import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from bot import handlers, callbacks, texts
from bot.api_client import ShadowTraderApi, ApiError, TelegramNotLinkedError
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

    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await dp.start_polling(bot)
    finally:
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())
