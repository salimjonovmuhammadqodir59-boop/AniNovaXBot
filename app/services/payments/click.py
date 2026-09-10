from __future__ import annotations

import hashlib
import time

from aiohttp import web
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import PaymentOrder, PaymentOrderStatus
from app.services.payments.common import fulfil_order, get_order

ERR_SUCCESS = 0
ERR_SIGN_FAILED = -1
ERR_INVALID_AMOUNT = -2
ERR_ORDER_NOT_FOUND = -5
ERR_ALREADY_PAID = -4
ERR_TRANSACTION_NOT_FOUND = -6
ERR_ACTION_NOT_FOUND = -3


def _sign(*parts: str) -> str:
    return hashlib.md5("".join(parts).encode()).hexdigest()


def _verify_prepare_sign(form: dict) -> bool:
    expected = _sign(
        form.get("click_trans_id", ""), form.get("service_id", ""), settings.CLICK_SECRET_KEY,
        form.get("merchant_trans_id", ""), form.get("amount", ""), form.get("action", ""),
        form.get("sign_time", ""),
    )
    return expected == form.get("sign_string")


def _verify_complete_sign(form: dict) -> bool:
    expected = _sign(
        form.get("click_trans_id", ""), form.get("service_id", ""), settings.CLICK_SECRET_KEY,
        form.get("merchant_trans_id", ""), form.get("merchant_prepare_id", ""),
        form.get("amount", ""), form.get("action", ""), form.get("sign_time", ""),
    )
    return expected == form.get("sign_string")


async def click_prepare(session: AsyncSession, form: dict) -> dict:
    if not _verify_prepare_sign(form):
        return {"error": ERR_SIGN_FAILED, "error_note": "Sign xato"}

    order = await get_order(session, form.get("merchant_trans_id", ""))
    if order is None:
        return {"error": ERR_ORDER_NOT_FOUND, "error_note": "Order topilmadi"}
    if order.status != PaymentOrderStatus.PENDING:
        return {"error": ERR_ALREADY_PAID, "error_note": "Order allaqachon yopilgan"}
    if int(float(form.get("amount", 0))) != order.amount:
        return {"error": ERR_INVALID_AMOUNT, "error_note": "Summasi noto'g'ri"}

    return {
        "click_trans_id": form.get("click_trans_id"),
        "merchant_trans_id": order.id,
        "merchant_prepare_id": order.id,
        "error": ERR_SUCCESS,
        "error_note": "OK",
    }


async def click_complete(session: AsyncSession, form: dict) -> dict:
    if not _verify_complete_sign(form):
        return {"error": ERR_SIGN_FAILED, "error_note": "Sign xato"}

    order = await get_order(session, form.get("merchant_trans_id", ""))
    if order is None:
        return {"error": ERR_ORDER_NOT_FOUND, "error_note": "Order topilmadi"}

    if str(form.get("error", "0")) not in ("0", ""):
        if order.status == PaymentOrderStatus.PENDING:
            order.status = PaymentOrderStatus.CANCELLED
            await session.commit()
        return {"click_trans_id": form.get("click_trans_id"), "merchant_trans_id": order.id,
                "merchant_confirm_id": order.id, "error": ERR_SUCCESS, "error_note": "Cancelled"}

    if order.status == PaymentOrderStatus.PAID:
        return {"click_trans_id": form.get("click_trans_id"), "merchant_trans_id": order.id,
                "merchant_confirm_id": order.id, "error": ERR_ALREADY_PAID, "error_note": "Allaqachon to'langan"}

    await fulfil_order(session, order, provider_transaction_id=str(form.get("click_trans_id")))

    return {
        "click_trans_id": form.get("click_trans_id"),
        "merchant_trans_id": order.id,
        "merchant_confirm_id": order.id,
        "error": ERR_SUCCESS,
        "error_note": "OK",
    }


async def click_webhook(request: web.Request) -> web.Response:
    from app.database.base import async_session

    form = dict(await request.post())
    action = form.get("action")

    async with async_session() as session:
        if action == "0":
            result = await click_prepare(session, form)
        elif action == "1":
            result = await click_complete(session, form)
        else:
            result = {"error": ERR_ACTION_NOT_FOUND, "error_note": "Action topilmadi"}

    return web.json_response(result)


def build_pay_url(order_id: str, amount_som: int) -> str:
    """amount must be in so'm (not tiyin) for Click."""
    return (
        f"https://my.click.uz/services/pay?service_id={settings.CLICK_SERVICE_ID}"
        f"&merchant_id={settings.CLICK_MERCHANT_ID}&amount={amount_som}"
        f"&transaction_param={order_id}&merchant_user_id={settings.CLICK_MERCHANT_USER_ID}"
    )
