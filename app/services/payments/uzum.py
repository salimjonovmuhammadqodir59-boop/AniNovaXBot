from __future__ import annotations

import base64
import time

from aiohttp import web
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import PaymeTransaction, PaymentOrder, PaymentOrderStatus
from app.services.payments.common import fulfil_order, get_order

# Uzum Bank's FastPay Merchant API follows the same JSON-RPC transaction state machine as Payme
# (check -> create -> perform/cancel). We reuse the PaymeTransaction table (provider-agnostic by
# design: it just tracks "a gateway transaction id -> order -> state") to avoid duplicating schema.

ERR_INVALID_AMOUNT = 1
ERR_ORDER_NOT_FOUND = 2
ERR_TRANSACTION_NOT_FOUND = 3
ERR_UNABLE_TO_PERFORM = 4
ERR_AUTH_FAILED = 5

STATE_CREATED = 1
STATE_PERFORMED = 2
STATE_CANCELLED = -1
STATE_CANCELLED_AFTER_PERFORM = -2


def _now_ms() -> int:
    return int(time.time() * 1000)


def check_auth(request: web.Request) -> bool:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header.removeprefix("Basic ")).decode()
        merchant_id, key = decoded.split(":", 1)
    except Exception:
        return False
    return merchant_id == settings.UZUM_MERCHANT_ID and key == settings.UZUM_SECRET_KEY


def rpc_error(request_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def rpc_result(request_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


async def _find_order(session: AsyncSession, params: dict) -> PaymentOrder | None:
    order_id = params.get("account", {}).get("order_id") or params.get("orderId")
    return await get_order(session, order_id) if order_id else None


async def handle_check(session: AsyncSession, req_id, params: dict) -> dict:
    order = await _find_order(session, params)
    if order is None:
        return rpc_error(req_id, ERR_ORDER_NOT_FOUND, "Order topilmadi")
    if order.status != PaymentOrderStatus.PENDING:
        return rpc_error(req_id, ERR_UNABLE_TO_PERFORM, "Order allaqachon yopilgan")
    if int(params.get("amount", 0)) != order.amount:
        return rpc_error(req_id, ERR_INVALID_AMOUNT, "Summasi noto'g'ri")
    return rpc_result(req_id, {"allow": True})


async def handle_create(session: AsyncSession, req_id, params: dict) -> dict:
    gateway_id = params["id"]
    existing = await session.get(PaymeTransaction, f"uzum:{gateway_id}")
    if existing is not None:
        return rpc_result(req_id, {"transaction": gateway_id, "state": existing.state, "create_time": existing.created_at_ms})

    order = await _find_order(session, params)
    if order is None:
        return rpc_error(req_id, ERR_ORDER_NOT_FOUND, "Order topilmadi")
    if order.status != PaymentOrderStatus.PENDING:
        return rpc_error(req_id, ERR_UNABLE_TO_PERFORM, "Order allaqachon yopilgan")

    created_ms = _now_ms()
    tx = PaymeTransaction(payme_id=f"uzum:{gateway_id}", order_id=order.id, amount=order.amount,
                           state=STATE_CREATED, created_at_ms=created_ms)
    session.add(tx)
    await session.commit()
    return rpc_result(req_id, {"transaction": gateway_id, "state": STATE_CREATED, "create_time": created_ms})


async def handle_perform(session: AsyncSession, req_id, params: dict) -> dict:
    gateway_id = params["id"]
    tx = await session.get(PaymeTransaction, f"uzum:{gateway_id}")
    if tx is None:
        return rpc_error(req_id, ERR_TRANSACTION_NOT_FOUND, "Tranzaksiya topilmadi")
    if tx.state == STATE_PERFORMED:
        return rpc_result(req_id, {"transaction": gateway_id, "state": tx.state, "perform_time": tx.perform_time_ms})

    tx.state = STATE_PERFORMED
    tx.perform_time_ms = _now_ms()
    await session.commit()

    order = await get_order(session, tx.order_id)
    if order is not None:
        await fulfil_order(session, order, provider_transaction_id=f"uzum:{gateway_id}")

    return rpc_result(req_id, {"transaction": gateway_id, "state": tx.state, "perform_time": tx.perform_time_ms})


async def handle_cancel(session: AsyncSession, req_id, params: dict) -> dict:
    gateway_id = params["id"]
    tx = await session.get(PaymeTransaction, f"uzum:{gateway_id}")
    if tx is None:
        return rpc_error(req_id, ERR_TRANSACTION_NOT_FOUND, "Tranzaksiya topilmadi")

    tx.state = STATE_CANCELLED_AFTER_PERFORM if tx.state == STATE_PERFORMED else STATE_CANCELLED
    tx.cancel_time_ms = _now_ms()

    order = await get_order(session, tx.order_id)
    if order is not None and order.status == PaymentOrderStatus.PENDING:
        order.status = PaymentOrderStatus.CANCELLED
    await session.commit()

    return rpc_result(req_id, {"transaction": gateway_id, "state": tx.state, "cancel_time": tx.cancel_time_ms})


METHODS = {
    "CheckTransaction": handle_check,
    "CreateTransaction": handle_create,
    "PerformTransaction": handle_perform,
    "CancelTransaction": handle_cancel,
}


async def uzum_webhook(request: web.Request) -> web.Response:
    from app.database.base import async_session

    if not check_auth(request):
        return web.json_response(rpc_error(None, ERR_AUTH_FAILED, "Ruxsat yo'q"), status=200)

    body = await request.json()
    method, params, req_id = body.get("method"), body.get("params", {}), body.get("id")
    handler = METHODS.get(method)
    if handler is None:
        return web.json_response(rpc_error(req_id, -32601, "Metod topilmadi"))

    async with async_session() as session:
        response = await handler(session, req_id, params)
    return web.json_response(response)


def build_pay_url(order_id: str, amount_som: int) -> str:
    return f"https://fastpay.uzumbank.uz/checkout?merchant={settings.UZUM_MERCHANT_ID}&order_id={order_id}&amount={amount_som}"
