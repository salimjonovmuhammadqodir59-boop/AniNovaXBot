from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.filters import IsAdmin
from app.admin.handlers.panel import log_admin_action
from app.admin.keyboards import admin_back_kb
from app.bot.states.states import AdminUserStates
from app.database.models import TransactionType, User
from app.services.coin_service import InsufficientCoinsError, change_balance
from app.services.referral_service import count_referrals
from app.services.vip_service import grant_vip_days, is_vip_active, vip_days_left

router = Router(name="admin_users")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "adm:users_menu")
async def users_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminUserStates.find_user)
    await callback.message.answer("👥 USERLAR\n\n🆔 Telegram ID orqali qidiring:")
    await callback.answer()


@router.message(AdminUserStates.find_user, F.text)
async def find_user(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.text.strip().isdigit():
        await message.answer("❗️ Faqat raqamli Telegram ID kiriting.")
        return
    await state.clear()
    user = await session.get(User, int(message.text.strip()))
    if user is None:
        await message.answer("❌ Bunday user topilmadi.")
        return
    await show_user_card(message, session, user)


async def show_user_card(message: Message, session: AsyncSession, user: User) -> None:
    referrals = await count_referrals(session, user.id)
    vip_line = f"Faol ({vip_days_left(user)} kun)" if is_vip_active(user) else "Faol emas"
    banned_text = "Ha" if user.is_banned else "Yo'q"
    text = (
        f"👤 @{user.username or '—'}\n"
        f"🆔 ID: {user.id}\n"
        f"🪙 Tanga: {user.coins}\n"
        f"👑 VIP: {vip_line}\n"
        f"👥 Referral: {referrals}\n"
        f"📅 Ro'yxatdan o'tgan: {user.created_at:%d.%m.%Y}\n"
        f"🕓 Oxirgi faollik: {user.last_active_at:%d.%m.%Y %H:%M}\n"
        f"👀 Ko'rilgan videolar: {user.total_views}\n"
        f"🪙 Sarflagan tanga: {user.total_spent_coins}\n"
        f"🚫 Bloklangan: {banned_text}"
    )
    ban_btn = ("🔓 Unban", f"adm:unban:{user.id}") if user.is_banned else ("🚫 Ban", f"adm:ban:{user.id}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ban_btn[0], callback_data=ban_btn[1]),
         InlineKeyboardButton(text="👑 VIP berish", callback_data=f"adm:grant_vip:{user.id}")],
        [InlineKeyboardButton(text="🪙 Tanga berish", callback_data=f"adm:grant_coins:{user.id}"),
         InlineKeyboardButton(text="🪙 Tanga olish", callback_data=f"adm:deduct_coins:{user.id}")],
        [InlineKeyboardButton(text="📩 Xabar yuborish", callback_data=f"adm:msg_user:{user.id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:home")],
    ])
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("adm:ban:"))
async def ban_user(callback: CallbackQuery, session: AsyncSession) -> None:
    user_id = int(callback.data.split(":")[-1])
    user = await session.get(User, user_id)
    if user:
        user.is_banned = True
        await session.commit()
        await log_admin_action(session, callback.from_user.id, "ban_user", f"user_id={user_id}")
        await show_user_card(callback.message, session, user)
    await callback.answer("🚫 Bloklandi")


@router.callback_query(F.data.startswith("adm:unban:"))
async def unban_user(callback: CallbackQuery, session: AsyncSession) -> None:
    user_id = int(callback.data.split(":")[-1])
    user = await session.get(User, user_id)
    if user:
        user.is_banned = False
        await session.commit()
        await log_admin_action(session, callback.from_user.id, "unban_user", f"user_id={user_id}")
        await show_user_card(callback.message, session, user)
    await callback.answer("🔓 Blok olindi")


@router.callback_query(F.data.startswith("adm:grant_vip:"))
async def grant_vip(callback: CallbackQuery, session: AsyncSession) -> None:
    user_id = int(callback.data.split(":")[-1])
    user = await session.get(User, user_id)
    if user:
        user = await grant_vip_days(session, user, 30)
        await log_admin_action(session, callback.from_user.id, "grant_vip", f"user_id={user_id} days=30")
        await show_user_card(callback.message, session, user)
    await callback.answer("👑 30 kunlik VIP berildi")


@router.callback_query(F.data.startswith("adm:grant_coins:"))
async def ask_grant_coins(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = int(callback.data.split(":")[-1])
    await state.set_state(AdminUserStates.grant_coins)
    await state.update_data(target_user_id=user_id)
    await callback.message.answer("🪙 Nechta tanga berilsin?")
    await callback.answer()


@router.message(AdminUserStates.grant_coins, F.text)
async def apply_grant_coins(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.text.strip().lstrip("-").isdigit():
        await message.answer("❗️ Faqat raqam kiriting.")
        return
    data = await state.get_data()
    user = await session.get(User, data["target_user_id"])
    await state.clear()
    if user is None:
        await message.answer("❌ User topilmadi.")
        return
    amount = int(message.text.strip())
    user = await change_balance(session, user, amount, TransactionType.ADMIN_GRANT, note="Admin tomonidan berildi")
    await log_admin_action(session, message.from_user.id, "grant_coins", f"user_id={user.id} amount={amount}")
    await message.answer(f"✅ {amount} tanga berildi. Yangi balans: {user.coins}")


@router.callback_query(F.data.startswith("adm:deduct_coins:"))
async def ask_deduct_coins(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = int(callback.data.split(":")[-1])
    await state.set_state(AdminUserStates.deduct_coins)
    await state.update_data(target_user_id=user_id)
    await callback.message.answer("🪙 Nechta tanga yechilsin?")
    await callback.answer()


@router.message(AdminUserStates.deduct_coins, F.text)
async def apply_deduct_coins(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.text.strip().isdigit():
        await message.answer("❗️ Faqat raqam kiriting.")
        return
    data = await state.get_data()
    user = await session.get(User, data["target_user_id"])
    await state.clear()
    if user is None:
        await message.answer("❌ User topilmadi.")
        return
    amount = int(message.text.strip())
    try:
        user = await change_balance(session, user, -amount, TransactionType.ADMIN_DEDUCT, note="Admin tomonidan yechildi")
    except InsufficientCoinsError:
        await message.answer("❗️ Userda yetarli tanga yo'q.")
        return
    await log_admin_action(session, message.from_user.id, "deduct_coins", f"user_id={user.id} amount={amount}")
    await message.answer(f"✅ {amount} tanga yechildi. Yangi balans: {user.coins}")


@router.callback_query(F.data.startswith("adm:msg_user:"))
async def ask_message_text(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = int(callback.data.split(":")[-1])
    await state.set_state(AdminUserStates.message_user)
    await state.update_data(target_user_id=user_id)
    await callback.message.answer("📩 Yubormoqchi bo'lgan matnni kiriting:")
    await callback.answer()


@router.message(AdminUserStates.message_user, F.text)
async def send_message_to_user(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await state.clear()
    try:
        await message.bot.send_message(chat_id=data["target_user_id"], text=f"📩 Admindan xabar:\n\n{message.text}")
        await message.answer("✅ Xabar yuborildi.")
    except Exception:
        await message.answer("❌ Xabar yuborilmadi (user botni bloklagan bo'lishi mumkin).")
