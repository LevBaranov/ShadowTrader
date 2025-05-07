import asyncio
import logging
from aiogram import Bot, Dispatcher

import handlers, callbacks

from config import settings

async def main():
    telegram_token = settings.telegram.token
    bot = Bot(token=telegram_token)
    dp = Dispatcher()
    dp.include_routers(handlers.router, callbacks.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())