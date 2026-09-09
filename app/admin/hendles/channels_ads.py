from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.filters import IsAdmin
from app.admin.handlers.panel import log_admin_action
from app.admin.keyboards import admin_back_kb
from app.bot.states.states import AdminAdStates, AdminChannelStates
from app.database.models import Advertisement
from app.database.settings_repo import set_setting
from app.services.channel_service import (
    SETTING_ANNOUNCE_CHANNEL, add_required_channel, get_required_channels, remove_required_channel,
)

router = Router(name="admin_channels_ads")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# ------------------------------------------------------------- channels ----
@router.callback_query(F.data == "adm:channels_menu")
async def channels_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    channels = await get_required_channels(session)
    rows = [[InlineKeyboardButton(text=f"❌ {c['title']}", callback_data=f"adm:channel_del:{c['chat_id']}")]
            for c in channels]
    rows.append([InlineKeyboardButton(text="➕ Majburiy kanal qo'shish", callback_data="adm:channel_add")])
    rows.append([InlineKeyboardButton(text="📢 E'lon kanalini sozlash", callback_data="adm:announce_channel_set")])
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:home")])
    text = "📢 KANALLAR\n\nMajburiy obuna kanallari (bosing — o'chirish):"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data == "adm:channel_add")
async def ask_channel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminChannelStates.waiting_forward_or_username)
    await state.update_data(mode="required")
    await callback.message.answer(
        "📢 Kanal @username sini yuboring (bot kanalda admin bo'lishi shart), format:\n@kanal_nomi"
    )
    await callback.answer()


@router.message(AdminChannelStates.waiting_forward_or_username, F.text)
async def receive_channel_username(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    username = message.text.strip()
    if not username.startswith("@"):
        await message.answer("❗️ @ bilan boshlanishi kerak. Masalan: @aninovax_channel")
        return

    try:
        chat = await message.bot.get_chat(username)
    except Exception:
        await message.answer("❌ Kanal topilmadi yoki bot u yerda admin emas.")
        return

    if data.get("mode") == "announce":
        await set_setting(session, SETTING_ANNOUNCE_CHANNEL, str(chat.id))
        await message.answer(f"✅ E'lon kanali sozlandi: {chat.title}")
    else:
        await add_required_channel(session, str(chat.id), chat.title, f"https://t.me/{username.lstrip('@')}")
        await message.answer(f"✅ Majburiy kanal qo'shildi: {chat.title}")

    await log_admin_action(session, message.from_user.id, "channel_add", username)
    await state.clear()


@router.callback_query(F.data == "adm:announce_channel_set")
async def ask_announce_channel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminChannelStates.waiting_forward_or_username)
    await state.update_data(mode="announce")
    await callback.message.answer("📢 Yangi animelar e'lon qilinadigan kanal @username sini yuboring:")
    await callback.answer()


@router.callback_query(F.data.startswith("adm:channel_del:"))
async def delete_channel(callback: CallbackQuery, session: AsyncSession) -> None:
    chat_id = callback.data.split(":", 2)[-1]
    await remove_required_channel(session, chat_id)
    await callback.answer("🗑 O'chirildi")
    await channels_menu(callback, session)


# ----------------------------------------------------------------- ads -----
@router.callback_query(F.data == "adm:ads_menu")
async def ads_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(select(Advertisement).order_by(Advertisement.created_at.desc()))
    ads = list(result.scalars().all())
    rows = [[InlineKeyboardButton(
        text=(ad.text or "(rasm)")[:30] + (" ❌" if not ad.is_active else ""),
        callback_data=f"adm:ad_detail:{ad.id}",
    )] for ad in ads]
    rows.append([InlineKeyboardButton(text="➕ Reklama qo'shish", callback_data="adm:ad_add")])
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:home")])
    await callback.message.edit_text("📢 REKLAMA BOSHQARUVI", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data == "adm:ad_add")
async def ad_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminAdStates.text)
    await callback.message.answer("📢 Reklama matnini kiriting (yoki /skip):")
    await callback.answer()


@router.message(AdminAdStates.text, F.text)
async def ad_add_text(message: Message, state: FSMContext) -> None:
    text = None if message.text.strip() == "/skip" else message.text.strip()
    await state.update_data(text=text)
    await state.set_state(AdminAdStates.photo)
    await message.answer("🖼 Rasm yuboring (yoki /skip):")


@router.message(AdminAdStates.photo, F.photo)
async def ad_add_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await state.set_state(AdminAdStates.button)
    await message.answer("🔗 Tugma matni va havolasini kiriting: MatnHavola formatida\nMasalan: Ko'rish|https://t.me/aninovax\n(yoki /skip)")


@router.message(AdminAdStates.photo, F.text, F.text == "/skip")
async def ad_skip_photo(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminAdStates.button)
    await message.answer("🔗 Tugma matni va havolasini kiriting: Matn|Havola formatida (yoki /skip)")


@router.message(AdminAdStates.button, F.text)
async def ad_add_button(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    button_text = button_url = None
    if message.text.strip() != "/skip" and "|" in message.text:
        button_text, button_url = [p.strip() for p in message.text.split("|", 1)]

    ad = Advertisement(
        text=data.get("text"), photo_file_id=data.get("photo_file_id"),
        button_text=button_text, button_url=button_url,
    )
    session.add(ad)
    await session.commit()
    await state.clear()
    await log_admin_action(session, message.from_user.id, "ad_add", f"ad_id={ad.id}")
    await message.answer("✅ Reklama qo'shildi.")


@router.callback_query(F.data.startswith("adm:ad_detail:"))
async def ad_detail(callback: CallbackQuery, session: AsyncSession) -> None:
    ad_id = int(callback.data.split(":")[-1])
    ad = await session.get(Advertisement, ad_id)
    if ad is None:
        await callback.answer("❌ Topilmadi", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Faolsizlantirish" if ad.is_active else "✅ Faollashtirish",
                               callback_data=f"adm:ad_toggle:{ad_id}")],
        [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"adm:ad_del:{ad_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:ads_menu")],
    ])
    await callback.message.answer(ad.text or "(matnsiz reklama)", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:ad_toggle:"))
async def toggle_ad(callback: CallbackQuery, session: AsyncSession) -> None:
    ad_id = int(callback.data.split(":")[-1])
    ad = await session.get(Advertisement, ad_id)
    if ad:
        ad.is_active = not ad.is_active
        await session.commit()
    await callback.answer("✅ Yangilandi")


@router.callback_query(F.data.startswith("adm:ad_del:"))
async def delete_ad(callback: CallbackQuery, session: AsyncSession) -> None:
    ad_id = int(callback.data.split(":")[-1])
    await session.execute(delete(Advertisement).where(Advertisement.id == ad_id))
    await session.commit()
    await callback.answer("🗑 O'chirildi")
    await ads_menu(callback, session)
