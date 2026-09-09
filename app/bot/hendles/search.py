from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.search import GENRES, genre_grid_kb, results_list_kb, search_menu_kb
from app.bot.states.states import SearchStates
from app.database.models import User
from app.services import anime_service

router = Router(name="search")

PAGE_SIZE = 8

LIST_FUNCS = {
    "latest": anime_service.latest_animes,
    "top_rated": anime_service.top_rated,
    "most_viewed": anime_service.most_viewed,
    "all": anime_service.all_animes_paginated,
}


@router.callback_query(F.data == "menu:search")
async def open_search_menu(callback: CallbackQuery) -> None:
    text = "🔎 ANIME IZLASH\n\n\"O'zingizga kerakli animeni qidirish usulini tanlang:\""
    await callback.message.answer(text, reply_markup=search_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "search:code")
async def ask_code(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SearchStates.waiting_code)
    await callback.message.answer("🔢 Anime kodini yuboring:\n\nMasalan:\n25")
    await callback.answer()


@router.message(SearchStates.waiting_code, F.text)
async def receive_code(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.text.strip().isdigit():
        await message.answer("❗️ Iltimos, faqat raqam yuboring. Masalan: 25")
        return
    await state.clear()
    anime = await anime_service.find_by_code(session, int(message.text.strip()))
    if anime is None:
        await message.answer("❌ Bunday kodli anime topilmadi.")
        return
    from app.bot.handlers.anime import send_anime_card
    await send_anime_card(message, session, anime)


@router.callback_query(F.data == "search:name")
async def ask_name(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SearchStates.waiting_name)
    await callback.message.answer("🔤 Anime nomini yozing:")
    await callback.answer()


@router.message(SearchStates.waiting_name, F.text)
async def receive_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    results = await anime_service.fuzzy_search_by_name(session, message.text.strip())
    if not results:
        await message.answer(f"❌ \"{message.text}\" bo'yicha hech narsa topilmadi.")
        return
    await state.update_data(name_results=[a.id for a in results])
    await show_name_results_page(message, state, page=0)


async def show_name_results_page(message: Message, state: FSMContext, page: int) -> None:
    from app.database.base import async_session

    data = await state.get_data()
    ids = data.get("name_results", [])
    start, end = page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE
    chunk_ids = ids[start:end]

    async with async_session() as session:
        items = []
        for anime_id in chunk_ids:
            anime = await anime_service.get_anime_by_id(session, anime_id)
            if anime:
                items.append((anime.id, anime.title))

    text = f"🔎 Natijalar ({len(ids)} ta topildi):"
    kb = results_list_kb(items, "list:name_results", page, has_prev=page > 0, has_next=end < len(ids))
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("list:name_results:"))
async def paginate_name_results(callback: CallbackQuery, state: FSMContext) -> None:
    page = int(callback.data.split(":")[-1])
    await show_name_results_page(callback.message, state, page)
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "search:genre")
async def open_genre_grid(callback: CallbackQuery) -> None:
    await callback.message.answer("📅 Janrni tanlang:", reply_markup=genre_grid_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("genre:pick:"))
async def pick_genre(callback: CallbackQuery, session: AsyncSession) -> None:
    idx = int(callback.data.split(":")[-1]) - 1
    if idx < 0 or idx >= len(GENRES):
        await callback.answer()
        return
    genre_name = GENRES[idx]
    from sqlalchemy import select
    from app.database.models import Genre

    result = await session.execute(select(Genre).where(Genre.name == genre_name))
    genre = result.scalar_one_or_none()
    if genre is None:
        await callback.message.answer(f"❌ \"{genre_name}\" janrida hozircha anime yo'q.")
        await callback.answer()
        return

    animes = await anime_service.list_by_genre(session, genre.id, page=0)
    if not animes:
        await callback.message.answer(f"❌ \"{genre_name}\" janrida hozircha anime yo'q.")
        await callback.answer()
        return

    items = [(a.id, a.title) for a in animes]
    kb = results_list_kb(items, f"list:genre_{genre.id}", 0, has_prev=False, has_next=len(animes) == 8,
                          back_cb="search:genre")
    await callback.message.answer(f"{genre_name} — animelar:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("list:genre_"))
async def paginate_genre(callback: CallbackQuery, session: AsyncSession) -> None:
    # format: list:genre_<id>:<page>
    body, page_str = callback.data.rsplit(":", 1)
    genre_id = int(body.split("_", 1)[1])
    page = int(page_str)
    animes = await anime_service.list_by_genre(session, genre_id, page=page)
    items = [(a.id, a.title) for a in animes]
    kb = results_list_kb(items, f"list:genre_{genre_id}", page, has_prev=page > 0, has_next=len(animes) == 8,
                          back_cb="search:genre")
    await callback.message.edit_text("Animelar:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "search:image")
async def ask_image(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SearchStates.waiting_image)
    await callback.message.answer("🖼 Anime posterining rasmini yuboring:")
    await callback.answer()


@router.message(SearchStates.waiting_image, F.photo)
async def receive_image(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    buf = await message.bot.download_file(file.file_path)
    anime = await anime_service.find_by_image_hash(session, buf.read())
    if anime is None:
        await message.answer("❌ Bu rasmga mos anime topilmadi.")
        return
    from app.bot.handlers.anime import send_anime_card
    await send_anime_card(message, session, anime)


@router.message(SearchStates.waiting_image)
async def receive_image_wrong_type(message: Message) -> None:
    await message.answer("❗️ Iltimos, rasm (photo) shaklida yuboring.")


@router.callback_query(F.data.startswith("list:"))
async def generic_list(callback: CallbackQuery, session: AsyncSession) -> None:
    # format: list:<kind>:<page>
    parts = callback.data.split(":")
    kind, page = parts[1], int(parts[2])
    if kind not in LIST_FUNCS:
        await callback.answer()
        return

    animes = await LIST_FUNCS[kind](session, page=page)
    titles = {"latest": "🔥 So'nggi yuklanganlar", "top_rated": "⭐ Reytingi baland",
              "most_viewed": "👀 Ko'p ko'rilgan", "all": "📚 Barcha animelar"}
    if not animes and page == 0:
        await callback.message.answer("❌ Hozircha bu bo'limda anime yo'q.")
        await callback.answer()
        return

    items = [(a.id, a.title) for a in animes]
    kb = results_list_kb(items, f"list:{kind}", page, has_prev=page > 0, has_next=len(animes) == PAGE_SIZE)
    try:
        await callback.message.edit_text(titles.get(kind, "Animelar:"), reply_markup=kb)
    except Exception:
        await callback.message.answer(titles.get(kind, "Animelar:"), reply_markup=kb)
    await callback.answer()
