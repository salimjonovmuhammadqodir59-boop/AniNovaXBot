from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Bot
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.services.channel_service import check_subscription, subscription_kb
from app.config import settings


class SubscriptionMiddleware(BaseMiddleware):
    """Blocks every update until the user has joined all required channels.
    The 'sub:check' callback itself is always allowed through so the user can retry."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, CallbackQuery) and event.data == "sub:check":
            return await handler(event, data)

        # Admins must always be able to access the admin panel, even when
        # mandatory channel subscription is enabled for normal users.
        from_user = getattr(event, "from_user", None)
        if from_user is not None and from_user.id in settings.admin_ids:
            return await handler(event, data)

        session = data.get("session")
        db_user = data.get("db_user")
        bot: Bot = data.get("bot")
        if session is None or db_user is None or bot is None:
            return await handler(event, data)

        missing = await check_subscription(bot, session, db_user.id)
        if not missing:
            return await handler(event, data)

        text = "📢 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling, so'ng \"✅ Tekshirish\" tugmasini bosing:"
        kb = subscription_kb(missing)
        if isinstance(event, Message):
            await event.answer(text, reply_markup=kb)
        elif isinstance(event, CallbackQuery):
            await event.answer("Avval kanallarga obuna bo'ling", show_alert=True)
            await event.message.answer(text, reply_markup=kb)
        return
