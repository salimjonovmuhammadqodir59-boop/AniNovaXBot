from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import CoinPackage, VipPlan


def coin_packages_kb(packages: list[CoinPackage]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text=f"{p.coins} tanga — {p.price:,} {p.currency}".replace(",", " "),
        callback_data=f"coins:buy:{p.id}",
    )] for p in packages]
    rows.append([InlineKeyboardButton(text="🎁 Kunlik bonus", callback_data="menu:bonus")])
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def bonus_kb(can_claim: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_claim:
        rows.append([InlineKeyboardButton(text="🎁 Bonusni olish", callback_data="bonus:claim")])
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def vip_menu_kb(plans: list[VipPlan], coin_threshold_days: int, coin_threshold: int,
                eligible_for_coin_vip: bool) -> InlineKeyboardMarkup:
    rows = []
    if eligible_for_coin_vip:
        rows.append([InlineKeyboardButton(
            text=f"👑 {coin_threshold} 🪙 → {coin_threshold_days} kun VIP",
            callback_data="vip:coins",
        )])
    for p in plans:
        if p.price_money:
            rows.append([InlineKeyboardButton(
                text=f"👑 {p.days} kun — {p.price_money:,} {p.currency}".replace(",", " "),
                callback_data=f"vip:money:{p.id}",
            )])
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
