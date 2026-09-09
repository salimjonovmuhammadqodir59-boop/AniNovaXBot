from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import Anime


def anime_card_kb(anime: Anime, back_cb: str = "menu:search") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="▶️ Tomosha qilish", callback_data=f"anime:episodes:{anime.id}:0")],
        [InlineKeyboardButton(text="📥 Yuklab olish", callback_data=f"anime:episodes:{anime.id}:0"),
         InlineKeyboardButton(text="❤️ Sevimlilarga qo'shish", callback_data=f"fav:add:{anime.id}")],
        [InlineKeyboardButton(text="⭐ Baholash", callback_data=f"anime:rate:{anime.id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=back_cb)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def anime_card_text(anime: Anime) -> str:
    genres = ", ".join(g.name for g in anime.genres) if anime.genres else "—"
    lines = [
        f"🎬 Anime nomi: {anime.title}\n",
        f"🆔 Anime ID: {anime.code}",
        f"📺 Qismlar: {len(anime.episodes)}",
    ]
    if anime.quality:
        lines.append(f"🎞 Sifat: {anime.quality}")
    lines.append(f"🎭 Janr: {genres}")
    lines.append(f"⭐ Reyting: {anime.average_rating} / 5")
    lines.append(f"👀 Ko'rishlar: {anime.views}")
    if anime.description:
        lines.append(f"\n📝 {anime.description}")
    return "\n".join(lines)


def episode_list_kb(anime_id: int, episodes: list, page: int, page_size: int = 6) -> InlineKeyboardMarkup:
    start = page * page_size
    chunk = episodes[start:start + page_size]
    numbers = "1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣"
    rows = []
    row = []
    for i, ep in enumerate(chunk):
        label = f"{numbers[i] if i < len(numbers) else i + 1} {ep.number}-qism"
        row.append(InlineKeyboardButton(text=label, callback_data=f"ep:open:{anime_id}:{ep.number}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"anime:episodes:{anime_id}:{page - 1}"))
    if start + page_size < len(episodes):
        nav.append(InlineKeyboardButton(text="➡️ Keyingi", callback_data=f"anime:episodes:{anime_id}:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"anime:open:{anime_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def episode_pay_kb(anime_id: int, number: int, price: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"▶️ Ko'rish — {price} 🪙", callback_data=f"ep:pay:{anime_id}:{number}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"anime:episodes:{anime_id}:0")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
