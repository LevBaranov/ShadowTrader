"""Точка входа планировщика.

Отдельный процесс бэкенда: ходит в БД и брокера через сервисный слой,
уведомляет пользователей через NotificationService.
Запуск: python -m src.scheduler.main
"""
import asyncio
import logging

from src.config import scheduler_settings
from src.logging_setup import setup_logging
from src.core.portfolio_manager import PortfolioManager
from src.db.database import async_session_maker
from src.scheduler.runner import (
    SchedulerRunner,
    ensure_bonds_offer_date_sync_task,
    ensure_index_sync_task,
    ensure_moex_bonds_sync_task,
)
from src.services.notifications import NotificationService

logger = logging.getLogger(__name__)


async def main():
    setup_logging()

    runner = SchedulerRunner(
        session_factory=async_session_maker,
        notifications=NotificationService(),
        portfolio_manager_factory=PortfolioManager,
    )

    interval = scheduler_settings.SCHEDULER_INTERVAL_SEC
    logger.info("Scheduler started, interval %s sec", interval)

    try:
        await ensure_index_sync_task(async_session_maker)
    except Exception:
        # Не роняем процесс: задача создастся при следующем старте,
        # а работу итераций это не блокирует.
        logger.exception("Failed to ensure index sync task")

    try:
        await ensure_moex_bonds_sync_task(async_session_maker)
    except Exception:
        logger.exception("Failed to ensure moex bonds sync task")

    try:
        await ensure_bonds_offer_date_sync_task(async_session_maker)
    except Exception:
        logger.exception("Failed to ensure bonds offer date sync task")

    while True:
        try:
            await runner.run_once()
        except Exception:
            # Ошибка одного прохода не должна убивать процесс.
            logger.exception("Scheduler iteration failed")
        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(main())
