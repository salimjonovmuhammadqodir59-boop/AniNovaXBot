from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.filters import IsAdmin
from app.admin.handlers.panel import log_admin_action
from app.admin.keyboards import admin_back_kb
from app.bot.states.states import AdminAnimeStates
from app.database.models import Anime, Episode
from app.services.anime_service import find_by_code, get_anime_by_id

router = Router(name="admin_anime_edit")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "adm:anime_menu")
async def anime_menu(callback: CallbackQuery) -> None:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Anime qo'shish", callback_data="adm:anime_add")],
        [InlineKeyboardButton(text="🔎 Anime topish (kod orqali)", callback_data="adm:anime_find")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:home")],
    ])
    await callback.message.edit_text("🎬 ANIME BOSHQARUVI", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "adm:anime_find")
async def ask_find_code(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminAnimeStates.edit_pick_field)
    await state.update_data(mode="find")
    await callback.message.answer("🔢 Anime kodini kiriting:")
    await callback.answer()


@router.message(AdminAnimeStates.edit_pick_field, F.text)
async def find_and_show(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    if data.get("mode") != "find" or not message.text.strip().isdigit():
        return
    anime = await find_by_code(session, int(message.text.strip()))
    if anime is None:
        await message.answer("❌ Topilmadi.")
        return
    await state.update_data(editing_anime_id=anime.id, mode=None)
    await show_edit_menu(message, anime.id)


async def show_edit_menu(message: Message, anime_id: int) -> None:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Nom", callback_data=f"adm:edit_field:{anime_id}:title"),
         InlineKeyboardButton(text="📝 Tavsif", callback_data=f"adm:edit_field:{anime_id}:description")],
        [InlineKeyboardButton(text="📅 Yil", callback_data=f"adm:edit_field:{anime_id}:year"),
         InlineKeyboardButton(text="⭐ Reyting", callback_data=f"adm:edit_field:{anime_id}:rating")],
        [InlineKeyboardButton(text="🔢 Kod", callback_data=f"adm:edit_field:{anime_id}:code"),
         InlineKeyboardButton(text="🎞 Sifat", callback_data=f"adm:edit_field:{anime_id}:quality")],
        [InlineKeyboardButton(text="🖼 Poster", callback_data=f"adm:edit_field:{anime_id}:poster"),
         InlineKeyboardButton(text="🖼 Banner", callback_data=f"adm:edit_field:{anime_id}:banner")],
        [InlineKeyboardButton(text="📺 Qism narxlari", callback_data=f"adm:episodes_prices:{anime_id}")],
        [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"adm:anime_delete:{anime_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:anime_menu")],
    ])
    await message.answer("✏️ O'zgartirish uchun bo'limni tanlang:", reply_markup=kb)


@router.callback_query(F.data.startswith("adm:edit_field:"))
async def pick_field(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, anime_id_str, field = callback.data.split(":")
    await state.set_state(AdminAnimeStates.edit_value)
    await state.update_data(editing_anime_id=int(anime_id_str), editing_field=field)
    prompts = {
        "title": "Yangi nomni kiriting:", "description": "Yangi tavsifni kiriting:",
        "year": "Yangi yilni kiriting (raqam):", "rating": "Yangi reytingni kiriting (0-5):",
        "code": "Yangi kodni kiriting (unikal raqam):", "quality": "Yangi sifatni kiriting:",
        "poster": "Yangi poster rasmini yuboring:", "banner": "Yangi banner rasmini yuboring:",
    }
    await callback.message.answer(prompts.get(field, "Yangi qiymatni kiriting:"))
    await callback.answer()


@router.message(AdminAnimeStates.edit_value, F.text)
async def apply_text_edit(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    field = data.get("editing_field")

    if field == "episode_price":
        if not message.text.strip().isdigit():
            await message.answer("❗️ Faqat raqam kiriting.")
            return
        episode = await session.get(Episode, data.get("editing_episode_id"))
        if episode:
            episode.price_coins = int(message.text.strip())
            episode.is_free = episode.price_coins == 0
            await session.commit()
            await message.answer(f"✅ Narx yangilandi: {episode.price_coins} tanga")
        await state.clear()
        return

    anime_id = data.get("editing_anime_id")
    if anime_id is None or field in (None, "poster", "banner"):
        return

    anime = await session.get(Anime, anime_id)
    if anime is None:
        await message.answer("❌ Anime topilmadi.")
        await state.clear()
        return

    text = message.text.strip()
    try:
        if field == "title":
            anime.title = text
        elif field == "description":
            anime.description = text
        elif field == "year":
            anime.year = int(text)
        elif field == "rating":
            stars = max(0.0, min(5.0, float(text.replace(",", "."))))
            anime.rating_sum, anime.rating_count = round(stars * 10), 1
        elif field == "code":
            if not text.isdigit():
                raise ValueError
            existing = await find_by_code(session, int(text))
            if existing and existing.id != anime.id:
                await message.answer("❗️ Bu kod band.")
                return
            anime.code = int(text)
        elif field == "quality":
            anime.quality = text
    except ValueError:
        await message.answer("❗️ Noto'g'ri format.")
        return

    await session.commit()
    await log_admin_action(session, message.from_user.id, f"anime_edit_{field}", f"anime_id={anime_id}")
    await state.clear()
    await message.answer("✅ Yangilandi.")
    await show_edit_menu(message, anime_id)


@router.message(AdminAnimeStates.edit_value, F.photo)
async def apply_photo_edit(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    anime_id, field = data.get("editing_anime_id"), data.get("editing_field")
    if anime_id is None or field not in ("poster", "banner"):
        return

    anime = await session.get(Anime, anime_id)
    if anime is None:
        return

    file_id = message.photo[-1].file_id
    if field == "poster":
        anime.poster_file_id = file_id
        from app.services.anime_service import compute_poster_dhash
        file = await message.bot.get_file(file_id)
        buf = await message.bot.download_file(file.file_path)
        anime.poster_dhash = await compute_poster_dhash(buf.read())
    else:
        anime.banner_file_id = file_id

    await session.commit()
    await state.clear()
    await message.answer("✅ Yangilandi.")
    await show_edit_menu(message, anime_id)


@router.callback_query(F.data.startswith("adm:anime_delete:"))
async def confirm_delete(callback: CallbackQuery) -> None:
    anime_id = int(callback.data.split(":")[-1])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"adm:anime_delete_confirm:{anime_id}"),
         InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm:anime_menu")],
    ])
    await callback.message.answer("⚠️ Haqiqatan ham bu animeni o'chirmoqchimisiz? (barcha qismlar bilan)", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:anime_delete_confirm:"))
async def delete_anime(callback: CallbackQuery, session: AsyncSession) -> None:
    anime_id = int(callback.data.split(":")[-1])
    await session.execute(delete(Anime).where(Anime.id == anime_id))
    await session.commit()
    await log_admin_action(session, callback.from_user.id, "anime_delete", f"anime_id={anime_id}")
    await callback.message.edit_text("🗑 O'chirildi.", reply_markup=admin_back_kb("adm:anime_menu"))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:episodes_prices:"))
async def list_episode_prices(callback: CallbackQuery, session: AsyncSession) -> None:
    anime_id = int(callback.data.split(":")[-1])
    anime = await get_anime_by_id(session, anime_id)
    if anime is None or not anime.episodes:
        await callback.answer("❌ Qismlar yo'q", show_alert=True)
        return
    rows = []
    for ep in anime.episodes:
        label = f"{ep.number}-qism — {'bepul' if ep.is_free else f'{ep.price_coins} 🪙'}{' (VIP bepul)' if ep.vip_free else ''}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"adm:ep_edit:{ep.id}")])
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:anime_menu")])
    await callback.message.answer(f"📺 {anime.title} — qism narxlari:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:ep_edit:"))
async def episode_edit_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    episode_id = int(callback.data.split(":")[-1])
    episode = await session.get(Episode, episode_id)
    if episode is None:
        await callback.answer("❌ Topilmadi", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆓 Bepul qilish", callback_data=f"adm:ep_free:{episode_id}:1"),
         InlineKeyboardButton(text="💰 Pullik qilish", callback_data=f"adm:ep_free:{episode_id}:0")],
        [InlineKeyboardButton(text="👑 VIP uchun bepul: yoqish", callback_data=f"adm:ep_vipfree:{episode_id}:1"),
         InlineKeyboardButton(text="👑 VIP uchun bepul: o'chirish", callback_data=f"adm:ep_vipfree:{episode_id}:0")],
        [InlineKeyboardButton(text="🪙 Narxni o'zgartirish", callback_data=f"adm:ep_setprice:{episode_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"adm:episodes_prices:{episode.anime_id}")],
    ])
    await callback.message.answer(f"📺 {episode.number}-qism sozlamalari:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:ep_free:"))
async def toggle_episode_free(callback: CallbackQuery, session: AsyncSession) -> None:
    _, _, ep_id_str, val = callback.data.split(":")
    episode = await session.get(Episode, int(ep_id_str))
    if episode:
        episode.is_free = bool(int(val))
        await session.commit()
    await callback.answer("✅ Yangilandi")


@router.callback_query(F.data.startswith("adm:ep_vipfree:"))
async def toggle_episode_vip_free(callback: CallbackQuery, session: AsyncSession) -> None:
    _, _, ep_id_str, val = callback.data.split(":")
    episode = await session.get(Episode, int(ep_id_str))
    if episode:
        episode.vip_free = bool(int(val))
        await session.commit()
    await callback.answer("✅ Yangilandi")


@router.callback_query(F.data.startswith("adm:ep_setprice:"))
async def ask_episode_new_price(callback: CallbackQuery, state: FSMContext) -> None:
    episode_id = int(callback.data.split(":")[-1])
    await state.set_state(AdminAnimeStates.edit_value)
    await state.update_data(editing_field="episode_price", editing_episode_id=episode_id, editing_anime_id=None)
    await callback.message.answer("🪙 Yangi narxni kiriting:")
    await callback.answer()
