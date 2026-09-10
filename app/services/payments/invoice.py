from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import settings
from app.database.models import CoinPackage, VipPlan
from app.database.base import async_session
from app.services.coin_service import get_or_create_user
from app.services.payments import click, payme, uzum
from app.services.payments.common import create_order


def _configured_providers() -> list[str]:
    providers = []
    if settings.PAYME_MERCHANT_ID and settings.PAYME_SECRET_KEY:
        providers.append("payme")
    if settings.CLICK_MERCHANT_ID and settings.CLICK_SECRET_KEY:
        providers.append("click")
    if settings.UZUM_MERCHANT_ID and settings.UZUM_SECRET_KEY:
        providers.append("uzum")
    return providers


def _pay_url(provider: str, order_id: str, amount_som: int) -> str:
    if provider == "payme":
        return payme.build_pay_url(order_id, amount_som * 100)  # Payme wants tiyin
    if provider == "click":
        return click.build_pay_url(order_id, amount_som)
    if provider == "uzum":
        return uzum.build_pay_url(order_id, amount_som)
    raise ValueError(provider)


async def _send_payment_choice(message: Message, kind: str, ref_id: int, amount_som: int, title: str) -> None:
    async with async_session() as session:
        user = await get_or_create_user(session, message.chat.id, None, None)
        providers = _configured_providers()

        if not providers:
            # SANDBOX MODE: no real gateway configured -- simulate an instant successful payment.
            order = await create_order(session, user, kind, ref_id, provider="test", amount=amount_som)
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ (TEST) To'lovni tasdiqlash", callback_data=f"pay:test:{order.id}")
            ]])
            pretty = f"{amount_som:,} so'm".replace(",", " ")
            await message.answer(f"🧪 SANDBOX rejim (payment provider sozlanmagan)\n\n{title}\n💰 {pretty}", reply_markup=kb)
            return

        rows = []
        first_order_id = None
        for provider in providers:
            order = await create_order(session, user, kind, ref_id, provider=provider, amount=amount_som)
            first_order_id = first_order_id or order.id
            url = _pay_url(provider, order.id, amount_som)
            label = {"payme": "💳 Payme orqali to'lash", "click": "💳 Click orqali to'lash",
                     "uzum": "💳 Uzum orqali to'lash"}[provider]
            rows.append([InlineKeyboardButton(text=label, url=url)])

        rows.append([InlineKeyboardButton(text="🔄 Holatni tekshirish", callback_data=f"pay:check:{first_order_id}")])
        pretty = f"{amount_som:,} so'm".replace(",", " ")
        await message.answer(f"{title}\n💰 {pretty}", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


async def send_coin_package_invoice(message: Message, package: CoinPackage) -> None:
    await _send_payment_choice(message, "coin_package", package.id, package.price, f"🪙 {package.coins} tanga")


async def send_vip_plan_invoice(message: Message, plan: VipPlan) -> None:
    await _send_payment_choice(message, "vip_plan", plan.id, plan.price_money, f"👑 {plan.days} kunlik VIP")
