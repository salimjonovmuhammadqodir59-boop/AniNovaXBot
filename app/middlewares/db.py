from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser

from app.database.base import async_session
from app.services.coin_service import get_or_create_user


class DbSessionMiddleware(BaseMiddleware):
    """Opens one SQLAlchemy AsyncSession per update and loads/creates the User row."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with async_session() as session:
            data["session"] = session

            tg_user: TgUser | None = data.get("event_from_user")
            if tg_user is not None:
                db_user = await get_or_create_user(
                    session, tg_user.id, tg_user.username, tg_user.full_name,
                )
                data["db_user"] = db_user

            return await handler(event, data)
