from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from app.database.models import User
from app.services.vip_service import is_vip_active


def main_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="🔎 Anime izlash",
                callback_data="menu:search",
            )
        ],
        [
            InlineKeyboardButton(
                text="🪙 Tanga & Bonus",
                callback_data="menu:coins",
            )
        ],
        [
            InlineKeyboardButton(
                text="👥 Do‘st taklif qilish",
                callback_data="menu:referral",
            )
        ],
        [
            InlineKeyboardButton(
                text="💎 VIP",
                callback_data="menu:vip",
            )
        ],
        [
            InlineKeyboardButton(
                text="📊 Statistika",
                callback_data="menu:stats",
            ),
        ],
        [
            InlineKeyboardButton(
                text="⚙️ Sozlamalar",
                callback_data="menu:settings",
            ),
        ],
    ]

    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_kb(callback_data: str = "menu:home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga",
                    callback_data=callback_data,
                )
            ]
        ]
    )


def greeting_text(user: User) -> str:
    vip_active = is_vip_active(user)

    vip_line = "💎 Faol"
    if not vip_active:
        vip_line = "❌ Faol emas"

    days = ""
    if vip_active and user.vip_expires_at:
        from app.services.vip_service import vip_days_left

        days = f"\n⏳ Tugashiga: {vip_days_left(user)} kun"

    name = user.full_name or "foydalanuvchi"

    return (
        f"👋 Assalomu alaykum, {name}!\n\n"
        f"🎬 AniNovaX Bot ga xush kelibsiz!\n"
        f"❤️ Sevimli animelaringizni toping va tomosha qiling.\n\n"
        f"🪙 Hisobingiz: {user.coins} tanga\n"
        f"🎁 Bugungi bonus: +50 tanga\n"
        f"👥 1 ta do‘st taklif: +50 tanga\n"
        f"💎 VIP: {vip_line}{days}"
            )
