from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.admin.handlers import anime_edit, anime_upload, broadcast, channels_ads, economy, panel, users
from app.bot.handlers import anime, main_menu, payments, search, start
from app.middlewares.db import DbSessionMiddleware
from app.middlewares.subscription import SubscriptionMiddleware
from app.middlewares.throttling import BanCheckMiddleware, ThrottlingMiddleware


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    # Order matters: DB session/user must load first, then ban check, then throttling,
    # then the mandatory-channel gate -- all before any handler runs.
    for observer in (dp.message, dp.callback_query):
        observer.middleware(DbSessionMiddleware())
        observer.middleware(BanCheckMiddleware())
        observer.middleware(ThrottlingMiddleware())
        observer.middleware(SubscriptionMiddleware())

    # Admin routers first so admin-only callbacks/commands are claimed before generic user routers.
    dp.include_router(panel.router)
    dp.include_router(anime_upload.router)
    dp.include_router(anime_edit.router)
    dp.include_router(users.router)
    dp.include_router(economy.router)
    dp.include_router(channels_ads.router)
    dp.include_router(broadcast.router)

    dp.include_router(start.router)
    dp.include_router(payments.router)
    dp.include_router(main_menu.router)
    dp.include_router(search.router)
    dp.include_router(anime.router)

    return dp
