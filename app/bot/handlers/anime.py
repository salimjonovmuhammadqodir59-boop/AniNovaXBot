from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.anime import anime_card_kb, anime_card_text, episode_list_kb, episode_pay_kb
from app.database.models import Anime, Favorite, User
from app.services import anime_service
from app.services.anime_service import NotEnoughCoinsError

router = Router(name="anime")


async def send_anime_card(message: Message, session: AsyncSession, anime: Anime, back_cb: str = "menu:search") -> None:
    anime = await anime_service.get_anime_by_id(session, anime.id)
    text = anime_card_text(anime)
    kb = anime_card_kb(anime, back_cb=back_cb)
    if anime.poster_file_id:
        await message.answer_photo(photo=anime.poster_file_id, caption=text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("anime:open:"))
async def open_anime(callback: CallbackQuery, session: AsyncSession) -> None:
    anime_id = int(callback.data.split(":")[-1])
    anime = await anime_service.get_anime_by_id(session, anime_id)
    if anime is None:
        await callback.answer("❌ Anime topilmadi", show_alert=True)
        return
    await send_anime_card(callback.message, session, anime)
    await callback.answer()


@router.callback_query(F.data.startswith("anime:episodes:"))
async def show_episodes(callback: CallbackQuery, session: AsyncSession) -> None:
    _, _, anime_id_str, page_str = callback.data.split(":")
    anime_id, page = int(anime_id_str), int(page_str)
    anime = await anime_service.get_anime_by_id(session, anime_id)
    if anime is None or not anime.episodes:
        await callback.answer("❌ Bu anime uchun qismlar hali yuklanmagan", show_alert=True)
        return

    text = f"🎬 {anime.title}\n📺 Qismlarni tanlang:"
    kb = episode_list_kb(anime_id, anime.episodes, page)
    await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("ep:open:"))
async def open_episode(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    _, _, anime_id_str, number_str = callback.data.split(":")
    anime_id, number = int(anime_id_str), int(number_str)

    episode = await anime_service.get_episode(session, anime_id, number)
    if episode is None:
        await callback.answer("❌ Qism topilmadi", show_alert=True)
        return

    price = await anime_service.preview_watch_price(session, db_user, episode)
    if price == 0:
        await deliver_episode(callback.message, session, db_user, episode)
        await callback.answer()
        return

    text = (
        f"🎬 Anime — {number}-qism\n\n"
        f"🪙 Narxi: {price} tanga\n"
        f"💰 Balansingiz: {db_user.coins} tanga"
    )
    await callback.message.answer(text, reply_markup=episode_pay_kb(anime_id, number, price))
    await callback.answer()


@router.callback_query(F.data.startswith("ep:pay:"))
async def pay_episode(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    _, _, anime_id_str, number_str = callback.data.split(":")
    anime_id, number = int(anime_id_str), int(number_str)

    episode = await anime_service.get_episode(session, anime_id, number)
    if episode is None:
        await callback.answer("❌ Qism topilmadi", show_alert=True)
        return

    try:
        await deliver_episode(callback.message, session, db_user, episode)
    except NotEnoughCoinsError:
        await callback.answer("❌ Balansingizda yetarli tanga yo'q. Tangalar bo'limidan to'ldiring.", show_alert=True)
        return
    await callback.answer("✅ Tomosha qilishingiz mumkin")


async def deliver_episode(message: Message, session: AsyncSession, user: User, episode) -> None:
    from app.services.anime_service import unlock_episode

    charged = await unlock_episode(session, user, episode)
    caption = f"🎬 {episode.number}-qism"
    if charged:
        caption += f"\n🪙 {charged} tanga yechildi"
    try:
        await message.answer_video(video=episode.video_file_id, caption=caption)
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    # Advertisement injection after every N total views, per active ad settings.
    from app.database.models import Advertisement
    from sqlalchemy import select

    if user.total_views and user.total_views % 5 == 0:
        result = await session.execute(select(Advertisement).where(Advertisement.is_active.is_(True)))
        ads = result.scalars().all()
        for ad in ads:
            if ad.target_audience == "non_vip" and user.is_vip:
                continue
            if user.total_views % max(ad.frequency_views, 1) != 0:
                continue
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
            kb = None
            if ad.button_text and ad.button_url:
                kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=ad.button_text, url=ad.button_url)]])
            if ad.photo_file_id:
                await message.answer_photo(photo=ad.photo_file_id, caption=ad.text or "", reply_markup=kb)
            elif ad.text:
                await message.answer(ad.text, reply_markup=kb)
            break


@router.callback_query(F.data.startswith("fav:add:"))
async def add_favorite(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    from sqlalchemy import select

    anime_id = int(callback.data.split(":")[-1])
    existing = await session.execute(
        select(Favorite).where(Favorite.user_id == db_user.id, Favorite.anime_id == anime_id)
    )
    if existing.scalar_one_or_none():
        await callback.answer("❤️ Bu anime allaqachon sevimlilarda", show_alert=True)
        return
    session.add(Favorite(user_id=db_user.id, anime_id=anime_id))
    await session.commit()
    await callback.answer("❤️ Sevimlilarga qo'shildi")


@router.callback_query(F.data.startswith("fav:remove:"))
async def remove_favorite(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    from sqlalchemy import delete

    anime_id = int(callback.data.split(":")[-1])
    await session.execute(delete(Favorite).where(Favorite.user_id == db_user.id, Favorite.anime_id == anime_id))
    await session.commit()
    await callback.answer("🗑 Sevimlilardan o'chirildi")
    from app.bot.handlers.main_menu import show_favorites
    await show_favorites(callback, session, db_user)


@router.callback_query(F.data.startswith("anime:rate:"))
async def ask_rating(callback: CallbackQuery) -> None:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    anime_id = int(callback.data.split(":")[-1])
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⭐" * i, callback_data=f"rate:set:{anime_id}:{i}") for i in range(1, 6)
    ]])
    await callback.message.answer("Ushbu animega bahoyingizni bering:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("rate:set:"))
async def set_rating(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    _, _, anime_id_str, stars_str = callback.data.split(":")
    anime_id, stars = int(anime_id_str), int(stars_str)
    anime = await anime_service.get_anime_by_id(session, anime_id)
    if anime is None:
        await callback.answer("❌ Anime topilmadi", show_alert=True)
        return
    anime = await anime_service.rate_anime(session, db_user.id, anime, stars)
    await callback.answer(f"✅ Bahoyingiz saqlandi: {'⭐' * stars}")
    await callback.message.edit_text(f"⭐ Yangi o'rtacha reyting: {anime.average_rating} / 5")
