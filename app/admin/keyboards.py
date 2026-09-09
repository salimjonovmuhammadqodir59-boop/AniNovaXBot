from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_main_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📊 Dashboard", callback_data="adm:dashboard"),
         InlineKeyboardButton(text="🎬 Anime boshqaruvi", callback_data="adm:anime_menu")],
        [InlineKeyboardButton(text="📤 Anime yuklash", callback_data="adm:anime_add"),
         InlineKeyboardButton(text="📺 Qism boshqaruvi", callback_data="adm:anime_menu")],
        [InlineKeyboardButton(text="🪙 Tanga boshqaruvi", callback_data="adm:coins_menu"),
         InlineKeyboardButton(text="👑 VIP boshqaruvi", callback_data="adm:vip_menu")],
        [InlineKeyboardButton(text="💳 To'lovlar", callback_data="adm:payments"),
         InlineKeyboardButton(text="👥 Userlar", callback_data="adm:users_menu")],
        [InlineKeyboardButton(text="📢 Reklama", callback_data="adm:ads_menu"),
         InlineKeyboardButton(text="📨 Broadcast", callback_data="adm:broadcast_start")],
        [InlineKeyboardButton(text="🎁 Bonus sozlamalari", callback_data="adm:bonus_settings"),
         InlineKeyboardButton(text="👥 Referral sozlamalari", callback_data="adm:referral_settings")],
        [InlineKeyboardButton(text="⚙️ Bot sozlamalari", callback_data="adm:bot_settings"),
         InlineKeyboardButton(text="📈 Statistika", callback_data="adm:dashboard")],
        [InlineKeyboardButton(text="📝 Loglar", callback_data="adm:logs"),
         InlineKeyboardButton(text="📢 Kanallar", callback_data="adm:channels_menu")],
        [InlineKeyboardButton(text="🔙 Chiqish", callback_data="adm:exit")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_back_kb(cb: str = "adm:home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data=cb)]])
