import asyncio
import logging
import signal

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent
from aiohttp import web

from bot import handlers, callbacks, texts
from bot.api_client import ShadowTraderApi, TelegramNotLinkedError
from bot.logging_setup import setup_logging
from bot.settings import BotSettings

logger = logging.getLogger(__name__)


def create_dispatcher(api: ShadowTraderApi, web_app_url: str) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    # Внедряется в хэндлеры по имени аргумента (aiogram workflow data).
    dp["api"] = api
    dp["web_app_url"] = web_app_url

    dp.include_routers(handlers.router, callbacks.router)

    @dp.errors()
    async def on_error(event: ErrorEvent):
        exception = event.exception
        message = None
        if event.update.message:
            message = event.update.message
        elif event.update.callback_query:
            message = event.update.callback_query.message

        if isinstance(exception, TelegramNotLinkedError):
            if message:
                await message.answer(texts.NOT_LINKED)
            return True

        logger.exception("Unhandled error in bot handler", exc_info=exception)
        if message:
            await message.answer(texts.GENERIC_ERROR)
        return True

    return dp


def build_webhook_app(
    bot: Bot,
    dp: Dispatcher,
    path: str,
    secret_token: str | None,
) -> web.Application:
    app = web.Application()

    async def handle(request: web.Request) -> web.Response:
        if secret_token:
            header_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if header_token != secret_token:
                logger.warning("Webhook request rejected: invalid secret token")
                return web.Response(status=403)
        try:
            payload = await request.json()
        except Exception:
            logger.exception("Webhook request has invalid JSON body")
            return web.Response(status=400)
        # feed_webhook_update сам декодирует raw dict в Update (context с bot).
        await dp.feed_webhook_update(bot, payload)
        return web.Response(status=200)

    app.router.add_post(path, handle)
    return app


async def run_webhook(bot: Bot, dp: Dispatcher, settings: BotSettings) -> None:
    if not settings.WEBHOOK_URL:
        raise ValueError("WEBHOOK_URL required when BOT_RUN_MODE=webhook")

    await bot.set_webhook(
        url=settings.WEBHOOK_URL,
        secret_token=settings.WEBHOOK_SECRET_TOKEN,
        drop_pending_updates=True,
    )
    logger.info("Webhook set: %s", settings.WEBHOOK_URL)

    app = build_webhook_app(bot, dp, settings.WEBHOOK_PATH, settings.WEBHOOK_SECRET_TOKEN)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.WEBHOOK_HOST, settings.WEBHOOK_PORT)
    await site.start()
    logger.info(
        "Webhook server listening on %s:%s%s",
        settings.WEBHOOK_HOST,
        settings.WEBHOOK_PORT,
        settings.WEBHOOK_PATH,
    )

    stop_event = asyncio.Event()

    def _signal_handler(signum, frame) -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            signal.signal(sig, _signal_handler)

    try:
        await stop_event.wait()
    finally:
        await site.stop()
        await runner.cleanup()
        await bot.delete_webhook()
        logger.info("Webhook server stopped")


async def run_polling(bot: Bot, dp: Dispatcher) -> None:
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


async def main():
    setup_logging()

    settings = BotSettings()

    api = ShadowTraderApi(
        base_url=settings.API_BASE_URL,
        service_key=settings.BOT_API_KEY,
    )

    session = None
    if settings.TELEGRAM_PROXY:
        from aiogram.client.session.aiohttp import AiohttpSession

        session = AiohttpSession(proxy=settings.TELEGRAM_PROXY)

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN, session=session)
    dp = create_dispatcher(api, settings.WEB_APP_URL)

    try:
        if settings.BOT_RUN_MODE == "webhook":
            await run_webhook(bot, dp, settings)
        elif settings.BOT_RUN_MODE == "polling":
            await run_polling(bot, dp)
        else:
            raise ValueError(
                f"Unknown BOT_RUN_MODE: {settings.BOT_RUN_MODE!r} "
                "(expected 'polling' or 'webhook')"
            )
    finally:
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())
