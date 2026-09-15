from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


# =========================
# JANRLAR
# =========================

GENRES = [
    "⚔️ Jangari",
    "😂 Komediya",
    "💕 Romantika",
    "🎭 Drama",
    "✨ Fantastika",
    "👻 Qo‘rqinchli",
    "🧠 Psixologik",
    "🏫 Maktab",
    "⚡ Tarixiy",
    "🥋 Jang san’ati",
    "🏆 Sport",
    "👨‍👩‍👧 Oila",
    "🌟 Sarguzasht",
    "🚀 Ilmiy-fantastika",
    "🕵️ Sirli",
    "🎨 Sehrli",
    "🌊 Hayotiy",
]


# =========================
# ANIME QIDIRISH MENYUSI
# =========================

def search_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="🔢 Kod orqali izlash",
                callback_data="search:code",
            )
        ],
        [
            InlineKeyboardButton(
                text="🔎 Nomi orqali izlash",
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
                text="🖼 Rasm orqali ma’lumot",
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
                text="👀
