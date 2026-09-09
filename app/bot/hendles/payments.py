from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import PaymentOrderStatus, User
from app.services.payments.common import fulfil_order, get_order

router = Router(name="payments")


@router.callback_query(F.data.startswith("pay:test:"))
async def confirm_test_payment(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    order_id = callback.data.split(":", 2)[-1]
    order = await get_order(session, order_id)
    if order is None or order.user_id != db_user.id:
        await callback.answer("❌ Order topilmadi", show_alert=True)
        return
    if order.status == PaymentOrderStatus.PAID:
        await callback.answer("✅ Bu order allaqachon to'langan", show_alert=True)
        return

    await fulfil_order(session, order, provider_transaction_id="TEST")
    kind_text = "tanga hisobingizga qo'shildi" if order.kind == "coin_package" else "VIP faollashtirildi"
    await callback.message.edit_text(f"✅ To'lov muvaffaqiyatli! {kind_text}.")
    await callback.answer("✅ To'landi (test rejimi)")


@router.callback_query(F.data.startswith("pay:check:"))
async def check_payment_status(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    order_id = callback.data.split(":", 2)[-1]
    order = await get_order(session, order_id)
    if order is None or order.user_id != db_user.id:
        await callback.answer("❌ Order topilmadi", show_alert=True)
        return

    if order.status == PaymentOrderStatus.PAID:
        await callback.answer("✅ To'lov tasdiqlangan!", show_alert=True)
    elif order.status == PaymentOrderStatus.CANCELLED:
        await callback.answer("❌ To'lov bekor qilingan", show_alert=True)
    else:
        await callback.answer("⏳ To'lov hali tasdiqlanmagan. To'lovni amalga oshirgach biroz kuting.", show_alert=True)
