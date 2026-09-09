from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import User
from app.services.vip_service import is_vip_active


def main_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🔎 Anime izlash", callback_data="menu:search"),
         InlineKeyboardButton(text="🪙 Tangalar & Bonus", callback_data="menu:coins")],
        [InlineKeyboardButton(text="👥 Do'st taklif qilish", callback_data="menu:referral"),
         InlineKeyboardButton(text="👑 VIP obuna", callback_data="menu:vip")],
        [InlineKeyboardButton(text="🔥 So'nggi yuklanganlar", callback_data="list:latest:0"),
         InlineKeyboardButton(text="🏆 Reyting", callback_data="menu:rating")],
        [InlineKeyboardButton(text="📚 Barcha animelar", callback_data="list:all:0"),
         InlineKeyboardButton(text="📋 Anime ro'yxati", callback_data="list:all:0")],
        [InlineKeyboardButton(text="🎁 Bonuslar", callback_data="menu:bonus"),
         InlineKeyboardButton(text="👤 Profil", callback_data="menu:profile")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="menu:stats"),
         InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="menu:settings")],
        [InlineKeyboardButton(text="📰 Yangiliklar", callback_data="menu:news")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_kb(callback_data: str = "menu:home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data=callback_data)]])


def greeting_text(user: User) -> str:
    vip_line = "Faol" if is_vip_active(user) else "Faol emas"
    days = ""
    if is_vip_active(user) and user.vip_expires_at:
        from app.services.vip_service import vip_days_left
        days = f"\n📅 Tugashiga: {vip_days_left(user)} kun"

    name = user.full_name or "foydalanuvchi"
    return (
        f"👋 Assalomu alaykum, {name}!\n\n"
        f"🎬 AniNovaXBot ga xush kelibsiz.\n"
        f"📺 Sevimli animelaringizni toping va tomosha qiling.\n\n"
        f"🪙 Tangalar: {user.coins}\n"
        f"👑 VIP: {vip_line}{days}"
    )
