from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.filters import IsAdmin
from app.admin.keyboards import admin_back_kb, admin_main_kb
from app.database.models import AdminLog, PaymentOrder, PaymentOrderStatus
from app.database.settings_repo import all_settings
from app.services.stats_service import admin_dashboard

router = Router(name="admin_panel")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(Command("admin"))
async def open_admin(message: Message) -> None:
    await message.answer("🔐 ADMIN PANEL", reply_markup=admin_main_kb())


@router.callback_query(F.data == "adm:home")
async def admin_home(callback: CallbackQuery) -> None:
    await callback.message.edit_text("🔐 ADMIN PANEL", reply_markup=admin_main_kb())
    await callback.answer()


@router.callback_query(F.data == "adm:exit")
async def admin_exit(callback: CallbackQuery) -> None:
    await callback.message.delete()
    await callback.answer("Admin paneldan chiqildi")


@router.callback_query(F.data == "adm:dashboard")
async def show_dashboard(callback: CallbackQuery, session: AsyncSession) -> None:
    d = await admin_dashboard(session)
    text = (
        "📊 DASHBOARD\n\n"
        f"👥 Jami userlar: {d['total_users']}\n"
        f"🟢 Aktiv userlar (7 kun): {d['active_users']}\n"
        f"👑 VIP userlar: {d['vip_users']}\n"
        f"🎬 Jami animelar: {d['total_animes']}\n"
        f"📺 Jami qismlar: {d['total_episodes']}\n"
        f"👀 Jami ko'rishlar: {d['total_views']}\n"
        f"🪙 Muomaladagi tangalar: {d['coins_in_circulation']}\n"
        f"💰 Bugungi daromad: {d['today_revenue']:,} so'm\n"
        f"💰 Oylik daromad: {d['month_revenue']:,} so'm\n"
        f"💳 Jami to'lovlar: {d['total_payments']}"
    ).replace(",", " ")
    await callback.message.edit_text(text, reply_markup=admin_back_kb())
    await callback.answer()


@router.callback_query(F.data == "adm:payments")
async def show_payments(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(
        select(PaymentOrder).where(PaymentOrder.status == PaymentOrderStatus.PAID)
        .order_by(PaymentOrder.paid_at.desc()).limit(10)
    )
    orders = list(result.scalars().all())
    if not orders:
        text = "💳 TO'LOVLAR\n\nHozircha to'lovlar yo'q."
    else:
        lines = ["💳 SO'NGGI TO'LOVLAR:\n"]
        for o in orders:
            lines.append(f"#{o.id[:8]} — {o.amount:,} so'm — {o.provider} — user {o.user_id}".replace(",", " "))
        text = "\n".join(lines)
    await callback.message.edit_text(text, reply_markup=admin_back_kb())
    await callback.answer()


@router.callback_query(F.data == "adm:logs")
async def show_logs(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(select(AdminLog).order_by(AdminLog.created_at.desc()).limit(15))
    logs = list(result.scalars().all())
    if not logs:
        text = "📝 LOGLAR\n\nHozircha loglar yo'q."
    else:
        lines = ["📝 SO'NGGI AMALLAR:\n"]
        for log in logs:
            lines.append(f"{log.created_at:%d.%m %H:%M} — admin {log.admin_id} — {log.action}")
        text = "\n".join(lines)
    await callback.message.edit_text(text, reply_markup=admin_back_kb())
    await callback.answer()


@router.callback_query(F.data == "adm:bot_settings")
async def show_bot_settings(callback: CallbackQuery, session: AsyncSession) -> None:
    s = await all_settings(session)
    text = (
        "⚙️ BOT SOZLAMALARI\n\n"
        f"🔁 Video ko'rish rejimi: {s['watch_access_mode']}\n"
        f"🎁 Kunlik bonus (bazaviy): {s['daily_bonus_base']}\n"
        f"⏱ Bonus cooldown: {s['daily_bonus_cooldown_hours']} soat\n"
        f"👥 Referral bonusi: {s['referral_bonus_coins']} tanga\n"
        f"👑 Tanga → VIP: {s['coins_to_vip_threshold']} tanga = {s['coins_to_vip_days']} kun\n\n"
        "O'zgartirish uchun tegishli bo'limlardan foydalaning (Tanga/VIP/Bonus/Referral boshqaruvi)."
    )
    await callback.message.edit_text(text, reply_markup=admin_back_kb())
    await callback.answer()


async def log_admin_action(session: AsyncSession, admin_id: int, action: str, details: str | None = None) -> None:
    session.add(AdminLog(admin_id=admin_id, action=action, details=details))
    await session.commit()
