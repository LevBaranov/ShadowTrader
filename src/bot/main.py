import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage


import handlers, callbacks

from src.config import settings
from src.bot.scheduler import Scheduler

async def main():
    telegram_token = settings.telegram.token
    bot = Bot(token=telegram_token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_routers(handlers.router, callbacks.router)

    await bot.delete_webhook(drop_pending_updates=True)

    scheduler = Scheduler()
    asyncio.create_task(scheduler.rebalance_scheduler())

    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())