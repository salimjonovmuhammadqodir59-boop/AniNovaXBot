from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.filters import IsAdmin
from app.admin.handlers.panel import log_admin_action
from app.admin.keyboards import admin_back_kb
from app.bot.states.states import AdminCoinPackageStates, AdminSettingsStates, AdminVipPlanStates
from app.database.models import CoinPackage, VipPlan
from app.database.settings_repo import get_setting, set_setting

router = Router(name="admin_economy")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# =================================================================== coins ==
@router.callback_query(F.data == "adm:coins_menu")
async def coins_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(select(CoinPackage).order_by(CoinPackage.sort_order))
    packages = list(result.scalars().all())
    rows = [[InlineKeyboardButton(
        text=f"{p.coins} 🪙 — {p.price:,} {p.currency}".replace(",", " ") + (" ❌" if not p.is_active else ""),
        callback_data=f"adm:coin_pkg:{p.id}",
    )] for p in packages]
    rows.append([InlineKeyboardButton(text="➕ Paket qo'shish", callback_data="adm:coin_pkg_add")])
    rows.append([InlineKeyboardButton(text="🔁 Ko'rish rejimini almashtirish", callback_data="adm:toggle_watch_mode")])
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:home")])
    watch_mode = await get_setting(session, "watch_access_mode")
    await callback.message.edit_text(f"🪙 TANGA BOSHQARUVI\n\nJoriy ko'rish rejimi: {watch_mode}",
                                      reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data == "adm:toggle_watch_mode")
async def toggle_watch_mode(callback: CallbackQuery, session: AsyncSession) -> None:
    current = await get_setting(session, "watch_access_mode")
    new_value = "pay_once" if current == "pay_every_time" else "pay_every_time"
    await set_setting(session, "watch_access_mode", new_value)
    await log_admin_action(session, callback.from_user.id, "toggle_watch_mode", new_value)
    await callback.answer(f"✅ Yangi rejim: {new_value}", show_alert=True)
    await coins_menu(callback, session)


@router.callback_query(F.data == "adm:coin_pkg_add")
async def add_package_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminCoinPackageStates.coins)
    await callback.message.answer("🪙 Nechta tanga? (masalan 100)")
    await callback.answer()


@router.message(AdminCoinPackageStates.coins, F.text)
async def add_package_coins(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit():
        await message.answer("❗️ Faqat raqam.")
        return
    await state.update_data(coins=int(message.text.strip()))
    await state.set_state(AdminCoinPackageStates.price)
    await message.answer("💰 Narxi (so'm)? (masalan 5000)")


@router.message(AdminCoinPackageStates.price, F.text)
async def add_package_price(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.text.strip().isdigit():
        await message.answer("❗️ Faqat raqam.")
        return
    data = await state.get_data()
    package = CoinPackage(coins=data["coins"], price=int(message.text.strip()), currency="UZS")
    session.add(package)
    await session.commit()
    await state.clear()
    await log_admin_action(session, message.from_user.id, "coin_package_add", f"{package.coins} coins / {package.price}")
    await message.answer(f"✅ Paket qo'shildi: {package.coins} tanga — {package.price:,} so'm".replace(",", " "))


@router.callback_query(F.data.startswith("adm:coin_pkg:"))
async def package_detail(callback: CallbackQuery, session: AsyncSession) -> None:
    pkg_id = int(callback.data.split(":")[-1])
    package = await session.get(CoinPackage, pkg_id)
    if package is None:
        await callback.answer("❌ Topilmadi", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Faolsizlantirish" if package.is_active else "✅ Faollashtirish",
                               callback_data=f"adm:coin_pkg_toggle:{pkg_id}")],
        [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"adm:coin_pkg_del:{pkg_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:coins_menu")],
    ])
    await callback.message.answer(f"{package.coins} tanga — {package.price:,} {package.currency}".replace(",", " "),
                                   reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:coin_pkg_toggle:"))
async def toggle_package(callback: CallbackQuery, session: AsyncSession) -> None:
    pkg_id = int(callback.data.split(":")[-1])
    package = await session.get(CoinPackage, pkg_id)
    if package:
        package.is_active = not package.is_active
        await session.commit()
    await callback.answer("✅ Yangilandi")


@router.callback_query(F.data.startswith("adm:coin_pkg_del:"))
async def delete_package(callback: CallbackQuery, session: AsyncSession) -> None:
    pkg_id = int(callback.data.split(":")[-1])
    await session.execute(delete(CoinPackage).where(CoinPackage.id == pkg_id))
    await session.commit()
    await callback.answer("🗑 O'chirildi")
    await coins_menu(callback, session)


# ===================================================================== vip ==
@router.callback_query(F.data == "adm:vip_menu")
async def vip_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(select(VipPlan).order_by(VipPlan.sort_order))
    plans = list(result.scalars().all())
    threshold = await get_setting(session, "coins_to_vip_threshold")
    threshold_days = await get_setting(session, "coins_to_vip_days")

    rows = [[InlineKeyboardButton(
        text=f"{p.days} kun — {p.price_money or 0:,} so'm".replace(",", " ") + (" ❌" if not p.is_active else ""),
        callback_data=f"adm:vip_plan:{p.id}",
    )] for p in plans]
    rows.append([InlineKeyboardButton(text="➕ Reja qo'shish", callback_data="adm:vip_plan_add")])
    rows.append([InlineKeyboardButton(text="🪙 Tanga→VIP chegarasini o'zgartirish", callback_data="adm:set_coins_vip")])
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:home")])

    text = f"👑 VIP BOSHQARUVI\n\n{threshold} 🪙 = {threshold_days} kun VIP (default)"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data == "adm:set_coins_vip")
async def ask_coins_vip_threshold(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminSettingsStates.waiting_value)
    await state.update_data(setting_key="coins_to_vip_threshold_and_days")
    await callback.message.answer("🪙➡️👑 Formatni kiriting: <tanga> <kun>\nMasalan: 500 30")
    await callback.answer()


@router.message(AdminSettingsStates.waiting_value, F.text)
async def apply_generic_setting(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    key = data.get("setting_key")
    parts = message.text.strip().split()

    if key == "coins_to_vip_threshold_and_days":
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            await message.answer("❗️ Format: 500 30")
            return
        await set_setting(session, "coins_to_vip_threshold", int(parts[0]))
        await set_setting(session, "coins_to_vip_days", int(parts[1]))
        await message.answer(f"✅ Yangilandi: {parts[0]} 🪙 = {parts[1]} kun VIP")

    elif key == "referral_bonus_coins":
        if not parts or not parts[0].isdigit():
            await message.answer("❗️ Faqat raqam kiriting.")
            return
        await set_setting(session, "referral_bonus_coins", int(parts[0]))
        await message.answer(f"✅ Referral bonusi: {parts[0]} tanga")

    elif key == "daily_bonus_cooldown_hours":
        if not parts or not parts[0].isdigit():
            await message.answer("❗️ Faqat raqam kiriting (soat).")
            return
        await set_setting(session, "daily_bonus_cooldown_hours", int(parts[0]))
        await message.answer(f"✅ Cooldown: {parts[0]} soat")

    elif key == "daily_bonus_streak":
        try:
            values = [int(x) for x in message.text.replace(",", " ").split()]
            if not values:
                raise ValueError
        except ValueError:
            await message.answer("❗️ Masalan: 10 15 20 30 45 70 100")
            return
        await set_setting(session, "daily_bonus_streak", values)
        await message.answer(f"✅ Streak jadvali yangilandi: {values}")

    await log_admin_action(session, message.from_user.id, f"setting_{key}", message.text)
    await state.clear()


@router.callback_query(F.data == "adm:vip_plan_add")
async def add_plan_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminVipPlanStates.days)
    await callback.message.answer("👑 Necha kunlik reja? (masalan 90)")
    await callback.answer()


@router.message(AdminVipPlanStates.days, F.text)
async def add_plan_days(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit():
        await message.answer("❗️ Faqat raqam.")
        return
    await state.update_data(days=int(message.text.strip()))
    await state.set_state(AdminVipPlanStates.price_coins)
    await message.answer("🪙 Tanga evaziga narxi? (agar bo'lmasa 0 kiriting)")


@router.message(AdminVipPlanStates.price_coins, F.text)
async def add_plan_price_coins(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit():
        await message.answer("❗️ Faqat raqam.")
        return
    await state.update_data(price_coins=int(message.text.strip()) or None)
    await state.set_state(AdminVipPlanStates.price_money)
    await message.answer("💰 Pul evaziga narxi (so'm)? (agar bo'lmasa 0 kiriting)")


@router.message(AdminVipPlanStates.price_money, F.text)
async def add_plan_price_money(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.text.strip().isdigit():
        await message.answer("❗️ Faqat raqam.")
        return
    data = await state.get_data()
    plan = VipPlan(days=data["days"], price_coins=data.get("price_coins"),
                    price_money=int(message.text.strip()) or None, currency="UZS")
    session.add(plan)
    await session.commit()
    await state.clear()
    await log_admin_action(session, message.from_user.id, "vip_plan_add", f"{plan.days} kun")
    await message.answer(f"✅ VIP reja qo'shildi: {plan.days} kun")


@router.callback_query(F.data.startswith("adm:vip_plan:"))
async def plan_detail(callback: CallbackQuery, session: AsyncSession) -> None:
    plan_id = int(callback.data.split(":")[-1])
    plan = await session.get(VipPlan, plan_id)
    if plan is None:
        await callback.answer("❌ Topilmadi", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Faolsizlantirish" if plan.is_active else "✅ Faollashtirish",
                               callback_data=f"adm:vip_plan_toggle:{plan_id}")],
        [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"adm:vip_plan_del:{plan_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:vip_menu")],
    ])
    text = f"👑 {plan.days} kun\n🪙 Tanga narxi: {plan.price_coins or '—'}\n💰 Pul narxi: {plan.price_money or '—'} so'm"
    await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:vip_plan_toggle:"))
async def toggle_plan(callback: CallbackQuery, session: AsyncSession) -> None:
    plan_id = int(callback.data.split(":")[-1])
    plan = await session.get(VipPlan, plan_id)
    if plan:
        plan.is_active = not plan.is_active
        await session.commit()
    await callback.answer("✅ Yangilandi")


@router.callback_query(F.data.startswith("adm:vip_plan_del:"))
async def delete_plan(callback: CallbackQuery, session: AsyncSession) -> None:
    plan_id = int(callback.data.split(":")[-1])
    await session.execute(delete(VipPlan).where(VipPlan.id == plan_id))
    await session.commit()
    await callback.answer("🗑 O'chirildi")
    await vip_menu(callback, session)


# ============================================================ bonus/referral
@router.callback_query(F.data == "adm:bonus_settings")
async def bonus_settings_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    cooldown = await get_setting(session, "daily_bonus_cooldown_hours")
    streak = await get_setting(session, "daily_bonus_streak")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏱ Cooldown vaqtini o'zgartirish", callback_data="adm:set_bonus_cooldown")],
        [InlineKeyboardButton(text="🔥 Streak jadvalini o'zgartirish", callback_data="adm:set_bonus_streak")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:home")],
    ])
    await callback.message.edit_text(f"🎁 BONUS SOZLAMALARI\n\n⏱ Cooldown: {cooldown} soat\n🔥 Streak: {streak}",
                                      reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "adm:set_bonus_cooldown")
async def ask_bonus_cooldown(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminSettingsStates.waiting_value)
    await state.update_data(setting_key="daily_bonus_cooldown_hours")
    await callback.message.answer("⏱ Yangi cooldown (soat) kiriting:")
    await callback.answer()


@router.callback_query(F.data == "adm:set_bonus_streak")
async def ask_bonus_streak(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminSettingsStates.waiting_value)
    await state.update_data(setting_key="daily_bonus_streak")
    await callback.message.answer("🔥 7 kunlik jadvalni bo'sh joy bilan kiriting:\nMasalan: 10 15 20 30 45 70 100")
    await callback.answer()


@router.callback_query(F.data == "adm:referral_settings")
async def referral_settings_menu(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    bonus = await get_setting(session, "referral_bonus_coins")
    await state.set_state(AdminSettingsStates.waiting_value)
    await state.update_data(setting_key="referral_bonus_coins")
    await callback.message.edit_text(f"👥 REFERRAL SOZLAMALARI\n\nJoriy bonus: {bonus} tanga\n\nYangi qiymatni kiriting:",
                                      reply_markup=admin_back_kb())
    await callback.answer()
