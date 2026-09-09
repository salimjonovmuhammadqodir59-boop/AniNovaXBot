from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from app.bot.setup import build_dispatcher
from app.config import settings
from app.database.base import init_db
from app.services.payments.click import click_webhook
from app.services.payments.payme import payme_webhook
from app.services.payments.uzum import uzum_webhook

logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("aninovax")


def register_payment_routes(app: web.Application) -> None:
    app.router.add_post("/pay/payme", payme_webhook)
    app.router.add_post("/pay/click", click_webhook)
    app.router.add_post("/pay/uzum", uzum_webhook)
    app.router.add_get("/health", lambda request: web.json_response({"status": "ok"}))


async def run_webhook(bot: Bot, dp: Dispatcher) -> None:
    await bot.set_webhook(settings.full_webhook_url, drop_pending_updates=True)

    app = web.Application()
    register_payment_routes(app)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=settings.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.WEBAPP_HOST, settings.WEBAPP_PORT)
    await site.start()
    logger.info("Webhook server started on %s:%s", settings.WEBAPP_HOST, settings.WEBAPP_PORT)

    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


async def run_payments_only_server() -> web.AppRunner:
    """Used alongside long-polling (local dev) so Payme/Click/Uzum webhooks still work."""
    app = web.Application()
    register_payment_routes(app)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.PAYMENTS_WEBAPP_HOST, settings.PAYMENTS_WEBAPP_PORT)
    await site.start()
    logger.info("Payments webhook server started on %s:%s", settings.PAYMENTS_WEBAPP_HOST, settings.PAYMENTS_WEBAPP_PORT)
    return runner


async def run_polling(bot: Bot, dp: Dispatcher) -> None:
    await bot.delete_webhook(drop_pending_updates=True)
    payments_runner = await run_payments_only_server()
    try:
        await dp.start_polling(bot)
    finally:
        await payments_runner.cleanup()


async def main() -> None:
    await init_db()

    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher()

    if settings.USE_WEBHOOK:
        await run_webhook(bot, dp)
    else:
        await run_polling(bot, dp)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi")
