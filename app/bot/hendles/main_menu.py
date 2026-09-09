from datetime import timedelta

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.coins import bonus_kb, coin_packages_kb, vip_menu_kb
from app.bot.keyboards.main import back_kb
from app.database.models import Advertisement, CoinPackage, User, VipPlan
from app.database.settings_repo import get_setting
from app.services.bonus_service import BonusOnCooldownError, claim_daily_bonus
from app.services.referral_service import count_referrals
from app.services.stats_service import favorites_list, user_stats
from app.services.vip_service import is_vip_active, vip_days_left

router = Router(name="main_menu")


# ---------------------------------------------------------------- coins ----
@router.callback_query(F.data == "menu:coins")
async def show_coins(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    result = await session.execute(select(CoinPackage).where(CoinPackage.is_active.is_(True)).order_by(CoinPackage.sort_order))
    packages = list(result.scalars().all())
    text = f"🪙 TANGALAR\n\nBalansingiz: {db_user.coins} tanga\n\n💳 Tanga sotib olish:"
    await callback.message.answer(text, reply_markup=coin_packages_kb(packages))
    await callback.answer()


@router.callback_query(F.data.startswith("coins:buy:"))
async def buy_coins(callback: CallbackQuery, session: AsyncSession) -> None:
    from app.services.payments.invoice import send_coin_package_invoice

    package_id = int(callback.data.split(":")[-1])
    package = await session.get(CoinPackage, package_id)
    if package is None or not package.is_active:
        await callback.answer("❌ Paket topilmadi", show_alert=True)
        return
    await send_coin_package_invoice(callback.message, package)
    await callback.answer()


# ---------------------------------------------------------------- bonus ----
@router.callback_query(F.data == "menu:bonus")
async def show_bonus(callback: CallbackQuery, db_user: User) -> None:
    cooldown_hours = 24
    can_claim = True
    text = "🎁 KUNLIK BONUS\n\n"
    if db_user.last_bonus_at is not None:
        from datetime import datetime, timezone
        elapsed = datetime.now(timezone.utc) - db_user.last_bonus_at
        remaining = timedelta(hours=cooldown_hours) - elapsed
        if remaining.total_seconds() > 0:
            can_claim = False
            hours, rem = divmod(int(remaining.total_seconds()), 3600)
            minutes = rem // 60
            text += f"⏳ Keyingi bonusgacha: {hours} soat {minutes} daqiqa\n"

    if can_claim:
        text += "Bugungi bonusingiz tayyor!\n\n🎁 Bosing va oling"
    text += f"\n🔥 Streak: {db_user.bonus_streak}-kun"
    await callback.message.answer(text, reply_markup=bonus_kb(can_claim))
    await callback.answer()


@router.callback_query(F.data == "bonus:claim")
async def claim_bonus(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    try:
        user, coins, day = await claim_daily_bonus(session, db_user)
    except BonusOnCooldownError as e:
        hours, rem = divmod(int(e.retry_after.total_seconds()), 3600)
        minutes = rem // 60
        await callback.answer(f"⏳ Yana {hours} soat {minutes} daqiqadan so'ng oling", show_alert=True)
        return

    await callback.message.edit_text(
        f"🎁 +{coins} tanga oldingiz!\n🔥 Streak: {day}-kun\n💰 Yangi balans: {user.coins} tanga",
    )
    await callback.answer("✅ Bonus qo'shildi!")


# ---------------------------------------------------------------- referral -
@router.callback_query(F.data == "menu:referral")
async def show_referral(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    from app.config import settings as cfg

    link = f"https://t.me/{cfg.BOT_USERNAME}?start=ref_{db_user.id}"
    bonus = await get_setting(session, "referral_bonus_coins")
    total = await count_referrals(session, db_user.id)
    text = (
        "👥 DO'ST TAKLIF QILISH\n\n"
        f"Har bir taklif qilingan do'stingiz uchun +{bonus} tanga olasiz!\n\n"
        f"🔗 Sizning havolangiz:\n{link}\n\n"
        f"👥 Jami taklif qilganlar: {total}"
    )
    await callback.message.answer(text, reply_markup=back_kb())
    await callback.answer()


# ---------------------------------------------------------------- vip -------
@router.callback_query(F.data == "menu:vip")
async def show_vip(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    result = await session.execute(select(VipPlan).where(VipPlan.is_active.is_(True)).order_by(VipPlan.sort_order))
    plans = list(result.scalars().all())
    threshold = await get_setting(session, "coins_to_vip_threshold")
    threshold_days = await get_setting(session, "coins_to_vip_days")

    vip_line = f"✅ Faol ({vip_days_left(db_user)} kun qoldi)" if is_vip_active(db_user) else "❌ Faol emas"
    text = (
        "👑 VIP OBUNA\n\n"
        f"Holatingiz: {vip_line}\n\n"
        f"{threshold} tanga evaziga {threshold_days} kunlik VIP faollashtirish mumkin, "
        "yoki pul orqali quyidagi rejalardan birini tanlang:"
    )
    eligible = db_user.coins >= threshold
    await callback.message.answer(text, reply_markup=vip_menu_kb(plans, threshold_days, threshold, eligible))
    await callback.answer()


@router.callback_query(F.data == "vip:coins")
async def buy_vip_coins(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    from app.services.vip_service import grant_vip_days
    from app.database.models import TransactionType
    from app.services.coin_service import change_balance, InsufficientCoinsError

    threshold = await get_setting(session, "coins_to_vip_threshold")
    days = await get_setting(session, "coins_to_vip_days")
    try:
        user = await change_balance(session, db_user, -threshold, TransactionType.VIP_PURCHASE_COINS,
                                     note=f"VIP {days} kun (tangalar orqali)")
    except InsufficientCoinsError:
        await callback.answer("❌ Balansda yetarli tanga yo'q", show_alert=True)
        return
    user = await grant_vip_days(session, user, days)
    await callback.message.edit_text(f"👑 Tabriklaymiz! {days} kunlik VIP faollashtirildi.\n💰 Balans: {user.coins} tanga")
    await callback.answer("✅ VIP faollashtirildi")


@router.callback_query(F.data.startswith("vip:money:"))
async def buy_vip_money(callback: CallbackQuery, session: AsyncSession) -> None:
    from app.services.payments.invoice import send_vip_plan_invoice

    plan_id = int(callback.data.split(":")[-1])
    plan = await session.get(VipPlan, plan_id)
    if plan is None or not plan.is_active or not plan.price_money:
        await callback.answer("❌ Reja topilmadi", show_alert=True)
        return
    await send_vip_plan_invoice(callback.message, plan)
    await callback.answer()


# ---------------------------------------------------------------- rating ----
@router.callback_query(F.data == "menu:rating")
async def show_rating_menu(callback: CallbackQuery) -> None:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Eng yuqori baholanganlar", callback_data="list:top_rated:0")],
        [InlineKeyboardButton(text="👀 Eng ko'p ko'rilganlar", callback_data="list:most_viewed:0")],
        [InlineKeyboardButton(text="🔥 Eng mashhurlar", callback_data="list:latest:0")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:home")],
    ])
    await callback.message.answer("🏆 REYTING", reply_markup=kb)
    await callback.answer()


# ---------------------------------------------------------------- profile --
@router.callback_query(F.data == "menu:profile")
async def show_profile(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    referrals = await count_referrals(session, db_user.id)
    vip_line = f"Faol ({vip_days_left(db_user)} kun)" if is_vip_active(db_user) else "Faol emas"
    text = (
        "👤 PROFIL\n\n"
        f"👋 Ism: {db_user.full_name or '—'}\n"
        f"🆔 Telegram ID: {db_user.id}\n"
        f"📅 Ro'yxatdan o'tgan: {db_user.created_at.strftime('%d.%m.%Y')}\n"
        f"🪙 Tangalar: {db_user.coins}\n"
        f"👑 VIP: {vip_line}\n"
        f"👥 Taklif qilganlar: {referrals}\n"
        f"🎁 Bonus streak: {db_user.bonus_streak}-kun"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️ Sevimli animelar", callback_data="profile:favorites")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:home")],
    ])
    await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "profile:favorites")
async def show_favorites(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    animes = await favorites_list(session, db_user.id)
    if not animes:
        await callback.message.answer("❤️ Sizda hali sevimli animelar yo'q.", reply_markup=back_kb("menu:profile"))
        await callback.answer()
        return

    from app.bot.keyboards.search import results_list_kb
    items = [(a.id, a.title) for a in animes]
    kb = results_list_kb(items, "profile:favorites", 0, has_prev=False, has_next=False, back_cb="menu:profile")
    await callback.message.answer("❤️ Sevimli animelar:", reply_markup=kb)
    await callback.answer()


# ---------------------------------------------------------------- stats ----
@router.callback_query(F.data == "menu:stats")
async def show_stats(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    stats = await user_stats(session, db_user)
    text = (
        "📊 STATISTIKA\n\n"
        f"🎬 Ko'rgan animelar: {stats['animes_watched']}\n"
        f"📺 Ko'rgan qismlar: {stats['episodes_watched']}\n"
        f"🪙 Sarflagan tangalar: {stats['coins_spent']}\n"
        f"👥 Referrallar: {stats['referrals']}\n"
        f"🎁 Bonusdan olingan tangalar: {stats['bonus_earned']}"
    )
    await callback.message.answer(text, reply_markup=back_kb())
    await callback.answer()


# ---------------------------------------------------------------- settings -
@router.callback_query(F.data == "menu:settings")
async def show_settings(callback: CallbackQuery, db_user: User) -> None:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O'zbek tili", callback_data="noop")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:home")],
    ])
    await callback.message.answer("⚙️ SOZLAMALAR\n\nTilingiz: O'zbek 🇺🇿", reply_markup=kb)
    await callback.answer()


# ---------------------------------------------------------------- news ------
@router.callback_query(F.data == "menu:news")
async def show_news(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(
        select(Advertisement).where(Advertisement.is_active.is_(True)).order_by(Advertisement.created_at.desc()).limit(5)
    )
    ads = list(result.scalars().all())
    if not ads:
        await callback.message.answer("📰 Hozircha yangiliklar yo'q.", reply_markup=back_kb())
        await callback.answer()
        return
    for ad in ads:
        if ad.photo_file_id:
            await callback.message.answer_photo(photo=ad.photo_file_id, caption=ad.text or "")
        elif ad.text:
            await callback.message.answer(ad.text)
    await callback.message.answer("🔙", reply_markup=back_kb())
    await callback.answer()
