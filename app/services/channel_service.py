from __future__ import annotations

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Anime
from app.database.settings_repo import get_setting, set_setting

SETTING_REQUIRED_CHANNELS = "required_channels"  # list[dict(username, chat_id, title, url)]
SETTING_ANNOUNCE_CHANNEL = "announce_channel_id"  # str chat_id or @username, or "" if disabled


async def get_required_channels(session: AsyncSession) -> list[dict]:
    value = await get_setting(session, SETTING_REQUIRED_CHANNELS)
    return value or []


async def add_required_channel(session: AsyncSession, chat_id: str, title: str, url: str) -> None:
    channels = await get_required_channels(session)
    channels.append({"chat_id": chat_id, "title": title, "url": url})
    await set_setting(session, SETTING_REQUIRED_CHANNELS, channels)


async def remove_required_channel(session: AsyncSession, chat_id: str) -> None:
    channels = await get_required_channels(session)
    channels = [c for c in channels if c["chat_id"] != chat_id]
    await set_setting(session, SETTING_REQUIRED_CHANNELS, channels)


async def check_subscription(bot: Bot, session: AsyncSession, user_id: int) -> list[dict]:
    """Returns the list of channels the user is NOT subscribed to (empty list = fully subscribed)."""
    channels = await get_required_channels(session)
    missing = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch["chat_id"], user_id=user_id)
            if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
                missing.append(ch)
        except Exception:
            # If the bot can't verify (not admin in channel, wrong id, etc.) don't block the user.
            continue
    return missing


def subscription_kb(missing: list[dict]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"📢 {c['title']}", url=c["url"])] for c in missing]
    rows.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="sub:check")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def post_new_anime_to_channel(bot: Bot, session: AsyncSession, anime: Anime, bot_username: str) -> None:
    channel = await get_setting(session, SETTING_ANNOUNCE_CHANNEL)
    if not channel:
        return

    genres = ", ".join(g.name for g in anime.genres) if anime.genres else "—"
    caption = (
        f"🆕 Yangi anime qo'shildi!\n\n"
        f"🎬 {anime.title}\n"
        f"🎭 {genres}\n"
        f"📅 {anime.year or '—'}\n"
        f"🆔 Kodi: {anime.code}\n\n"
        f"👇 Tomosha qilish uchun botga o'ting"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="▶️ Botda ko'rish", url=f"https://t.me/{bot_username}?start=anime_{anime.code}")
    ]])
    try:
        if anime.banner_file_id:
            await bot.send_photo(chat_id=channel, photo=anime.banner_file_id, caption=caption, reply_markup=kb)
        elif anime.poster_file_id:
            await bot.send_photo(chat_id=channel, photo=anime.poster_file_id, caption=caption, reply_markup=kb)
        else:
            await bot.send_message(chat_id=channel, text=caption, reply_markup=kb)
    except Exception:
        pass  # channel not configured correctly -- doesn't block the admin's upload flow
