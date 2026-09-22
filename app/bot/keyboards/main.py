from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from app.database.models import User
from app.services.vip_service import is_vip_active


def main_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="🔎 Anime Izlash",
                callback_data="menu:search"
            )
        ],
        [
            InlineKeyboardButton(
                text="🪙 Tangalar",
                callback_data="menu:coins"
            ),
            InlineKeyboardButton(
                text="🎁 Kunlik bonus",
                callback_data="menu:bonus"
            )
        ],
        [
            InlineKeyboardButton(
                text="👥 Do‘st taklif qilish",
                callback_data="menu:referral"
            ),
            InlineKeyboardButton(
                text="🏆 Reyting",
                callback_data="menu:rating"
            )
        ],
        [
            InlineKeyboardButton(
                text="👤 Profil",
                callback_data="menu:profile"
            ),
            InlineKeyboardButton(
                text="👑 VIP",
                callback_data="menu:vip"
            )
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
        f"🎬 <b>AniNovaX Bot</b> ga xush kelibsiz!\n\n"
        f"❤️ Sevimli animelaringizni biz bilan tomosha qiling!\n\n"
        f"🪙 Hisobingiz: <b>{user.coins} tanga</b>\n"
        f"🎁 Bugungi bonus: <b>+50 tanga</b>\n"
        f"👥 Do‘st taklifi: <b>+50 tanga</b>\n"
        f"{vip_line}{days}\n\n"
        f"👇 Kerakli bo‘limni tanlang:"
)
