from __future__ import annotations

import base64
import time

from aiohttp import web
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import PaymentOrder, PaymentOrderStatus, PaymeTransaction
from app.services.payments.common import fulfil_order, get_order

# Payme error codes, per https://developer.help.paycom.uz
ERR_INVALID_AMOUNT = -31001
ERR_TRANSACTION_NOT_FOUND = -31003
ERR_ORDER_NOT_FOUND = -31050
ERR_UNABLE_TO_PERFORM = -31008
ERR_UNABLE_TO_CANCEL = -31007
ERR_AUTH_FAILED = -32504

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
        login, key = decoded.split(":", 1)
    except Exception:
        return False
    return login == "Paycom" and key == settings.PAYME_SECRET_KEY


def rpc_error(request_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": {"uz": message, "ru": message, "en": message}}}


def rpc_result(request_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


async def find_order_for_account(session: AsyncSession, account: dict) -> PaymentOrder | None:
    order_id = account.get("order_id")
    if not order_id:
        return None
    return await get_order(session, order_id)


async def handle_check_perform_transaction(session: AsyncSession, req_id, params: dict) -> dict:
    order = await find_order_for_account(session, params.get("account", {}))
    if order is None:
        return rpc_error(req_id, ERR_ORDER_NOT_FOUND, "Order topilmadi")
    if order.status != PaymentOrderStatus.PENDING:
        return rpc_error(req_id, ERR_UNABLE_TO_PERFORM, "Order allaqachon yopilgan")
    if int(params.get("amount", 0)) != order.amount:
        return rpc_error(req_id, ERR_INVALID_AMOUNT, "Summasi noto'g'ri")
    return rpc_result(req_id, {"allow": True})


async def handle_create_transaction(session: AsyncSession, req_id, params: dict) -> dict:
    payme_id = params["id"]
    existing = await session.get(PaymeTransaction, payme_id)
    if existing is not None:
        order = await get_order(session, existing.order_id)
        return rpc_result(req_id, {
            "create_time": existing.created_at_ms, "transaction": existing.payme_id,
            "state": existing.state,
        })

    order = await find_order_for_account(session, params.get("account", {}))
    if order is None:
        return rpc_error(req_id, ERR_ORDER_NOT_FOUND, "Order topilmadi")
    if order.status != PaymentOrderStatus.PENDING:
        return rpc_error(req_id, ERR_UNABLE_TO_PERFORM, "Order allaqachon yopilgan")
    if int(params.get("amount", 0)) != order.amount:
        return rpc_error(req_id, ERR_INVALID_AMOUNT, "Summasi noto'g'ri")

    # Only one active (state=1) Payme transaction may exist per order at a time.
    result = await session.execute(
        select(PaymeTransaction).where(PaymeTransaction.order_id == order.id, PaymeTransaction.state == STATE_CREATED)
    )
    if result.scalar_one_or_none() is not None:
        return rpc_error(req_id, ERR_UNABLE_TO_PERFORM, "Boshqa tranzaksiya faol")

    created_ms = _now_ms()
    tx = PaymeTransaction(payme_id=payme_id, order_id=order.id, amount=order.amount,
                           state=STATE_CREATED, created_at_ms=created_ms)
    session.add(tx)
    await session.commit()
    return rpc_result(req_id, {"create_time": created_ms, "transaction": payme_id, "state": STATE_CREATED})


async def handle_perform_transaction(session: AsyncSession, req_id, params: dict) -> dict:
    payme_id = params["id"]
    tx = await session.get(PaymeTransaction, payme_id)
    if tx is None:
        return rpc_error(req_id, ERR_TRANSACTION_NOT_FOUND, "Tranzaksiya topilmadi")

    if tx.state == STATE_PERFORMED:
        return rpc_result(req_id, {"transaction": tx.payme_id, "perform_time": tx.perform_time_ms, "state": tx.state})
    if tx.state != STATE_CREATED:
        return rpc_error(req_id, ERR_UNABLE_TO_PERFORM, "Tranzaksiya yakunlangan")

    order = await get_order(session, tx.order_id)
    tx.state = STATE_PERFORMED
    tx.perform_time_ms = _now_ms()
    await session.commit()

    if order is not None:
        await fulfil_order(session, order, provider_transaction_id=payme_id)

    return rpc_result(req_id, {"transaction": tx.payme_id, "perform_time": tx.perform_time_ms, "state": tx.state})


async def handle_cancel_transaction(session: AsyncSession, req_id, params: dict) -> dict:
    payme_id = params["id"]
    reason = params.get("reason")
    tx = await session.get(PaymeTransaction, payme_id)
    if tx is None:
        return rpc_error(req_id, ERR_TRANSACTION_NOT_FOUND, "Tranzaksiya topilmadi")

    if tx.state == STATE_CREATED:
        tx.state = STATE_CANCELLED
    elif tx.state == STATE_PERFORMED:
        tx.state = STATE_CANCELLED_AFTER_PERFORM
    tx.reason = reason
    tx.cancel_time_ms = _now_ms()

    order = await get_order(session, tx.order_id)
    if order is not None and order.status == PaymentOrderStatus.PENDING:
        order.status = PaymentOrderStatus.CANCELLED
    await session.commit()

    return rpc_result(req_id, {"transaction": tx.payme_id, "cancel_time": tx.cancel_time_ms, "state": tx.state})


async def handle_check_transaction(session: AsyncSession, req_id, params: dict) -> dict:
    payme_id = params["id"]
    tx = await session.get(PaymeTransaction, payme_id)
    if tx is None:
        return rpc_error(req_id, ERR_TRANSACTION_NOT_FOUND, "Tranzaksiya topilmadi")
    return rpc_result(req_id, {
        "create_time": tx.created_at_ms, "perform_time": tx.perform_time_ms, "cancel_time": tx.cancel_time_ms,
        "transaction": tx.payme_id, "state": tx.state, "reason": tx.reason,
    })


async def handle_get_statement(session: AsyncSession, req_id, params: dict) -> dict:
    from_ms, to_ms = params.get("from", 0), params.get("to", _now_ms())
    result = await session.execute(
        select(PaymeTransaction).where(PaymeTransaction.created_at_ms.between(from_ms, to_ms))
    )
    transactions = [{
        "id": tx.payme_id, "time": tx.created_at_ms, "amount": tx.amount,
        "account": {"order_id": tx.order_id}, "create_time": tx.created_at_ms,
        "perform_time": tx.perform_time_ms, "cancel_time": tx.cancel_time_ms,
        "transaction": tx.payme_id, "state": tx.state, "reason": tx.reason,
    } for tx in result.scalars().all()]
    return rpc_result(req_id, {"transactions": transactions})


METHODS = {
    "CheckPerformTransaction": handle_check_perform_transaction,
    "CreateTransaction": handle_create_transaction,
    "PerformTransaction": handle_perform_transaction,
    "CancelTransaction": handle_cancel_transaction,
    "CheckTransaction": handle_check_transaction,
    "GetStatement": handle_get_statement,
}


async def payme_webhook(request: web.Request) -> web.Response:
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


def build_pay_url(order_id: str, amount_tiyin: int) -> str:
    """Builds a Payme checkout link. amount must be in tiyin (so'm * 100)."""
    base = "https://checkout.test.paycom.uz" if settings.PAYME_TEST_MODE else "https://checkout.paycom.uz"
    raw = f"m={settings.PAYME_MERCHANT_ID};ac.order_id={order_id};a={amount_tiyin}"
    encoded = base64.b64encode(raw.encode()).decode()
    return f"{base}/{encoded}"
