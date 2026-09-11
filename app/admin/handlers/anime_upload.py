from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.filters import IsAdmin
from app.admin.handlers.panel import log_admin_action
from app.admin.keyboards import admin_back_kb
from app.bot.keyboards.search import GENRES
from app.bot.states.states import AdminAnimeStates
from app.database.models import Anime, Episode, Genre
from app.database.settings_repo import get_setting
from app.services.anime_service import compute_poster_dhash
from app.services.channel_service import post_new_anime_to_channel

router = Router(name="admin_anime_upload")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def _finish_upload_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tugatish", callback_data="adm:anime_upload_finish")
    ]])


@router.callback_query(F.data == "adm:anime_add")
async def start_add_anime(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AdminAnimeStates.title)
    await callback.message.answer("➕ Anime qo'shish\n\n1️⃣ Anime nomini kiriting:")
    await callback.answer()


@router.message(AdminAnimeStates.title, F.text)
async def add_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(AdminAnimeStates.poster)
    await message.answer("2️⃣ Poster rasmini yuboring:")


@router.message(AdminAnimeStates.poster, F.photo)
async def add_poster(message: Message, state: FSMContext) -> None:
    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    buf = await message.bot.download_file(file.file_path)
    dhash = await compute_poster_dhash(buf.read())
    await state.update_data(poster_file_id=photo.file_id, poster_dhash=dhash)
    await state.set_state(AdminAnimeStates.banner)
    await message.answer("3️⃣ Banner rasmini yuboring (yoki /skip):")


@router.message(AdminAnimeStates.poster)
async def add_poster_wrong(message: Message) -> None:
    await message.answer("❗️ Iltimos, rasm (photo) yuboring.")


@router.message(AdminAnimeStates.banner, F.photo)
async def add_banner(message: Message, state: FSMContext) -> None:
    await state.update_data(banner_file_id=message.photo[-1].file_id)
    await state.set_state(AdminAnimeStates.description)
    await message.answer("4️⃣ Tavsifni kiriting:")


@router.message(AdminAnimeStates.banner, Command("skip"))
async def skip_banner(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminAnimeStates.description)
    await message.answer("4️⃣ Tavsifni kiriting:")


@router.message(AdminAnimeStates.description, F.text)
async def add_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip())
    await state.set_state(AdminAnimeStates.year)
    await message.answer("5️⃣ Yilini kiriting (masalan 2024):")


@router.message(AdminAnimeStates.year, F.text)
async def add_year(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit():
        await message.answer("❗️ Faqat raqam kiriting. Masalan: 2024")
        return
    await state.update_data(year=int(message.text.strip()), genre_ids=[])
    await state.set_state(AdminAnimeStates.genres)
    await message.answer("6️⃣ Janrlarini tanlang (bir nechtasini tanlash mumkin):", reply_markup=_genre_toggle_kb([]))


def _genre_toggle_kb(selected_indexes: list[int]) -> InlineKeyboardMarkup:
    rows, row = [], []
    for i, g in enumerate(GENRES, start=1):
        mark = "✅ " if i in selected_indexes else ""
        row.append(InlineKeyboardButton(text=f"{mark}{g}", callback_data=f"adm:genre_toggle:{i}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="✅ Tayyor", callback_data="adm:genre_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(AdminAnimeStates.genres, F.data.startswith("adm:genre_toggle:"))
async def toggle_genre(callback: CallbackQuery, state: FSMContext) -> None:
    idx = int(callback.data.split(":")[-1])
    data = await state.get_data()
    selected = data.get("genre_ids", [])
    if idx in selected:
        selected.remove(idx)
    else:
        selected.append(idx)
    await state.update_data(genre_ids=selected)
    await callback.message.edit_reply_markup(reply_markup=_genre_toggle_kb(selected))
    await callback.answer()


@router.callback_query(AdminAnimeStates.genres, F.data == "adm:genre_done")
async def genres_done(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminAnimeStates.rating)
    await callback.message.answer("7️⃣ Reytingni kiriting (0-5, masalan 4.8):")
    await callback.answer()


@router.message(AdminAnimeStates.rating, F.text)
async def add_rating(message: Message, state: FSMContext) -> None:
    try:
        rating = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❗️ Masalan: 4.8 formatida kiriting.")
        return
    await state.update_data(initial_rating=max(0.0, min(5.0, rating)))
    await state.set_state(AdminAnimeStates.quality)
    await message.answer("8️⃣ Sifatini kiriting (masalan: 720p / 1080p):")


@router.message(AdminAnimeStates.quality, F.text)
async def add_quality(message: Message, state: FSMContext) -> None:
    await state.update_data(quality=message.text.strip())
    await state.set_state(AdminAnimeStates.code)
    await message.answer("9️⃣ Anime kodini kiriting (unikal raqam, masalan 25):")


@router.message(AdminAnimeStates.code, F.text)
async def add_code(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.text.strip().isdigit():
        await message.answer("❗️ Faqat raqam kiriting.")
        return
    code = int(message.text.strip())

    from app.services.anime_service import find_by_code
    if await find_by_code(session, code) is not None:
        await message.answer("❗️ Bu kod band. Boshqa kod kiriting.")
        return

    data = await state.get_data()
    anime = Anime(
        code=code, title=data["title"], description=data.get("description"),
        poster_file_id=data.get("poster_file_id"), banner_file_id=data.get("banner_file_id"),
        poster_dhash=data.get("poster_dhash"), year=data.get("year"), quality=data.get("quality"),
    )
    # The admin-entered "reyting" seeds the crowd rating as a single initial vote (scaled x10 to
    # keep fractional precision in the Integer column, matching anime_service.rate_anime()).
    initial_rating = data.get("initial_rating", 0)
    if initial_rating:
        anime.rating_sum = round(initial_rating * 10)
        anime.rating_count = 1

    genre_ids = data.get("genre_ids", [])
    if genre_ids:
        names = [GENRES[i - 1] for i in genre_ids]
        result = await session.execute(select(Genre).where(Genre.name.in_(names)))
        existing = {g.name: g for g in result.scalars().all()}
        for name in names:
            if name not in existing:
                new_genre = Genre(name=name)
                session.add(new_genre)
                existing[name] = new_genre
        await session.flush()
        anime.genres = list(existing.values())

    session.add(anime)
    await session.commit()
    await session.refresh(anime)

    await state.set_state(AdminAnimeStates.uploading_videos)
    await state.update_data(anime_id=anime.id, next_episode=1)
    await log_admin_action(session, message.from_user.id, "anime_create", f"anime_id={anime.id} code={code}")

    await message.answer(
        f"✅ \"{anime.title}\" yaratildi (kod: {code}).\n\n"
        "📤 Endi videolarni ketma-ket yuboring. Har bir video avtomatik qism raqami bilan saqlanadi.\n"
        "Tugatgach \"✅ Tugatish\" tugmasini bosing.",
        reply_markup=_finish_upload_kb(),
    )


@router.message(AdminAnimeStates.uploading_videos, F.video)
async def receive_episode_video(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    anime_id = data["anime_id"]
    number = data.get("next_episode", 1)

    default_price = await get_setting(session, "default_episode_price")
    default_free = await get_setting(session, "default_episode_free")

    episode = Episode(
        anime_id=anime_id, number=number, video_file_id=message.video.file_id,
        price_coins=0 if default_free else default_price, is_free=bool(default_free),
    )
    session.add(episode)
    await session.commit()

    await state.update_data(next_episode=number + 1)
    price_text = "bepul" if episode.is_free else f"{episode.price_coins} tanga"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Narxni o'zgartirish", callback_data=f"adm:ep_price:{episode.id}")],
        [InlineKeyboardButton(text="✅ Tugatish", callback_data="adm:anime_upload_finish")],
    ])
    await message.answer(f"✅ {number}-qism qo'shildi ({price_text})", reply_markup=kb)


@router.callback_query(F.data.startswith("adm:ep_price:"))
async def ask_episode_price(callback: CallbackQuery, state: FSMContext) -> None:
    episode_id = int(callback.data.split(":")[-1])
    await state.update_data(editing_episode_price_id=episode_id)
    await callback.message.answer("🪙 Yangi narxni kiriting (0 = bepul):")
    await callback.answer()


@router.message(AdminAnimeStates.uploading_videos, F.text)
async def maybe_set_episode_price(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    episode_id = data.get("editing_episode_price_id")
    if episode_id is None or not message.text.strip().isdigit():
        return
    price = int(message.text.strip())
    episode = await session.get(Episode, episode_id)
    if episode:
        episode.price_coins = price
        episode.is_free = price == 0
        await session.commit()
        await message.answer(f"✅ {episode.number}-qism narxi yangilandi: {'bepul' if price == 0 else f'{price} tanga'}")
    await state.update_data(editing_episode_price_id=None)


@router.callback_query(F.data == "adm:anime_upload_finish")
async def finish_upload(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    anime_id = data.get("anime_id")
    await state.clear()

    if anime_id is None:
        await callback.answer()
        return

    from app.services.anime_service import get_anime_by_id
    from app.config import settings as cfg

    anime = await get_anime_by_id(session, anime_id)
    await callback.message.answer(f"✅ \"{anime.title}\" uchun {len(anime.episodes)} ta qism yuklandi.",
                                   reply_markup=admin_back_kb())
    await post_new_anime_to_channel(callback.bot, session, anime, cfg.BOT_USERNAME)
    await callback.answer("✅ Yakunlandi")
