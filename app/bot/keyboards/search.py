from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

GENRES = [
    "⚔️ Jangari", "😂 Komediya", "❤️ Romantika", "🎭 Drama",
    "🧙 Fantastika", "🗺️ Sarguzasht", "👻 Qo'rqinchli", "🧠 Psixologik",
    "🏫 Maktab", "🏰 Tarixiy", "🚀 Ilmiy fantastika", "🎯 Sport",
    "👨‍👩‍👧 Oila", "✨ Sehrli", "🥋 Jang san'ati",
]


def search_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🔢 Kod orqali izlash", callback_data="search:code"),
         InlineKeyboardButton(text="🔤 Nomi orqali izlash", callback_data="search:name")],
        [InlineKeyboardButton(text="📅 Janr orqali izlash", callback_data="search:genre"),
         InlineKeyboardButton(text="🔥 So'nggi yuklanganlar", callback_data="list:latest:0")],
        [InlineKeyboardButton(text="🖼 Rasm orqali ma'lumot", callback_data="search:image"),
         InlineKeyboardButton(text="📋 Nomi orqali ma'lumot", callback_data="search:name")],
        [InlineKeyboardButton(text="⭐ Reytingi baland", callback_data="list:top_rated:0"),
         InlineKeyboardButton(text="👀 Ko'p ko'rilgan", callback_data="list:most_viewed:0")],
        [InlineKeyboardButton(text="📚 Barcha animelar", callback_data="list:all:0"),
         InlineKeyboardButton(text="📨 Anime ro'yxati", callback_data="list:all:0")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def genre_grid_kb() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for i, g in enumerate(GENRES, start=1):
        row.append(InlineKeyboardButton(text=g, callback_data=f"genre:pick:{i}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:search")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def results_list_kb(items: list[tuple[int, str]], list_key: str, page: int, has_prev: bool, has_next: bool,
                     back_cb: str = "menu:search") -> InlineKeyboardMarkup:
    """items: list of (anime_id, title)."""
    numbers = "1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣8️⃣9️⃣🔟"
    rows = []
    for i, (anime_id, title) in enumerate(items):
        prefix = numbers[i] if i < len(numbers) else f"{i + 1}."
        rows.append([InlineKeyboardButton(text=f"{prefix} {title}", callback_data=f"anime:open:{anime_id}")])

    nav = []
    if has_prev:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"{list_key}:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}", callback_data="noop"))
    if has_next:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"{list_key}:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
