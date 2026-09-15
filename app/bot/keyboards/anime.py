from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import Anime


def anime_card_kb(
    anime: Anime,
    back_cb: str = "menu:search",
) -> InlineKeyboardMarkup:

    rows = [
        [
            InlineKeyboardButton(
                text="▶️ Tomosha qilish",
                callback_data=f"anime:episodes:{anime.id}:0",
            )
        ],
        [
            InlineKeyboardButton(
                text="📥 Yuklab olish",
                callback_data=f"anime:episodes:{anime.id}:0",
            ),
            InlineKeyboardButton(
                text="❤️ Sevimlilarga qo‘shish",
                callback_data=f"fav:add:{anime.id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="⭐ Baholash",
                callback_data=f"anime:rate:{anime.id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="⬅️ Orqaga",
                callback_data=back_cb,
            )
        ],
    ]

    return InlineKeyboardMarkup(inline_keyboard=rows)


def anime_card_text(anime: Anime) -> str:

    genres = (
        ", ".join(g.name for g in anime.genres)
        if anime.genres
        else "—"
    )

    lines = [
        f"🎬 Anime: {anime.title}",
        f"🆔 Kod: {anime.code}",
        f"📺 Qismlar: {len(anime.episodes)}",
    ]

    if anime.year:
        lines.append(f"📅 Yil: {anime.year}")

    if anime.quality:
        lines.append(f"🎞 Sifat: {anime.quality}")

    lines.append(f"🎭 Janr: {genres}")
    lines.append(f"⭐ Reyting: {anime.average_rating} / 5")
    lines.append(f"👀 Ko‘rishlar: {anime.views}")

    if anime.description:
        lines.append("")
        lines.append(f"📝 Tavsif: {anime.description}")

    return "\n".join(lines)


def episode_list_kb(
    anime_id: int,
    episodes: list,
    page: int,
    page_size: int = 6,
) -> InlineKeyboardMarkup:

    start = page * page_size
    chunk = episodes[start:start + page_size]

    rows = []
    row = []

    for ep in chunk:

        button = InlineKeyboardButton(
            text=f"🎬 {ep.number}-qism",
            callback_data=f"ep:open:{anime_id}:{ep.number}",
        )

        row.append(button)

        if len(row) == 2:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    navigation = []

    if start > 0:
        navigation.append(
            InlineKeyboardButton(
                text="⬅️ Oldingi",
                callback_data=(
                    f"anime:episodes:{anime_id}:{page - 1}"
                ),
            )
        )

    if start + page_size < len(episodes):
        navigation.append(
            InlineKeyboardButton(
                text="Keyingi ➡️",
                callback_data=(
                    f"anime:episodes:{anime_id}:{page + 1}"
                ),
            )
        )

    if navigation:
        rows.append(navigation)

    rows.append([
        InlineKeyboardButton(
            text="⬅️ Orqaga",
            callback_data=f"anime:open:{anime_id}",
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def episode_pay_kb(
    anime_id: int,
    number: int,
    price: int,
) -> InlineKeyboardMarkup:

    rows = [
        [
            InlineKeyboardButton(
                text=f"▶️ {number}-qismni ko‘rish • 🪙 {price} tanga",
                callback_data=f"ep:pay:{anime_id}:{number}",
            )
        ],
        [
            InlineKeyboardButton(
                text="⬅️ Orqaga",
                callback_data=f"anime:episodes:{anime_id}:0",
            )
        ],
    ]

    return InlineKeyboardMarkup(inline_keyboard=rows)
