from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


GENRES = [
    "💥 Jangari",
    "😂 Komediya",
    "❤️ Romantika",
    "🪄 Fantastika",
    "👻 Qo‘rqinchli",
    "🎭 Drama",
    "🧙 Sarguzasht",
    "🏫 Maktab",
    "⚔️ Sehr",
    "🤖 Fantastik",
    "🏆 Sport",
    "🎵 Musiqiy",
]


def search_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔢 Kodi orqali izlash",
                    callback_data="search:code",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔤 Nomi orqali izlash",
                    callback_data="search:name",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏷 Janr orqali izlash",
                    callback_data="search:genre",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🆕 So‘nggi qo‘shilganlar",
                    callback_data="search:latest",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🖼 Rasm orqali izlash",
                    callback_data="search:image",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Nomi bo‘yicha tartiblash",
                    callback_data="search:name_sort",
                )
            ],
            [
                InlineKeyboardButton(
                    text="👀 Ko‘p ko‘rilganlar",
                    callback_data="list:most_viewed:0",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📚 Barcha animelar",
                    callback_data="list:all:0",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga",
                    callback_data="menu:main",
                )
            ],
        ]
    )


def genre_grid_kb() -> InlineKeyboardMarkup:
    rows = []

    for i in range(0, len(GENRES), 2):
        row = []

        row.append(
            InlineKeyboardButton(
                text=GENRES[i],
                callback_data=f"genre:pick:{i}",
            )
        )

        if i + 1 < len(GENRES):
            row.append(
                InlineKeyboardButton(
                    text=GENRES[i + 1],
                    callback_data=f"genre:pick:{i + 1}",
                )
            )

        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga",
                callback_data="search:menu",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def genre_kb() -> InlineKeyboardMarkup:
    """
    Eski handlerlarda genre_kb nomi ishlatilgan.
    Shu sababli genre_grid_kb bilan bir xil keyboard qaytaradi.
    """
    return genre_grid_kb()


def results_list_kb(
    items,
    prefix: str,
    page: int = 0,
    has_prev: bool = False,
    has_next: bool = False,
) -> InlineKeyboardMarkup:

    rows = []

    for item_id, title in items:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🎬 {title}",
                    callback_data=f"anime:open:{item_id}",
                )
            ]
        )

    navigation = []

    if has_prev:
        navigation.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"{prefix}:{max(0, page - 1)}",
            )
        )

    if has_next:
        navigation.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"{prefix}:{page + 1}",
            )
        )

    if navigation:
        rows.append(navigation)

    rows.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga",
                callback_data="search:menu",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)
