import os
from datetime import datetime, timedelta
import asyncio
import logging

from aiogram import Bot
from aiogram.types import Message

from src.core.portfolio_manager import PortfolioManager
from src.config import settings, ConfigLoader
from src.db.repositories.user_repository import UserRepository

from src.models.scheduler_frequency import ScheduleFrequency

from src.db.database import get_session
from src.db.repositories.task_repository import TaskRepository
from src.db.enums import TaskType

def _save_result(obj: list):
    if not obj:
        return

    obj_type = type(obj[0]).__name__
    filename = f"{obj_type}s.txt"

    os.makedirs('../scheduler_results', exist_ok=True)

    filepath = os.path.join('../scheduler_results', filename)

    with open(filepath, 'a', encoding='utf-8') as f:
        for item in obj:
            f.write(f"[{datetime.now()}] {str(item)}\n")

logger = logging.getLogger(__name__)

class Scheduler:


    def __init__(self, bot: Bot = None):

        self.bot = bot

    async def _send_report(self, chat_id, type_report, **data) -> Message | None:

        if self.bot:

            head = "Я тут немного 'пошуршал' пока ты не видел.\n"
            if type_report == "rebalance":

                success_action_list = data.get("success_action_list")
                error_action_list = data.get("error_action_list")

                message = head + "Успешно:\n" + "\n".join( [
                    f"Действие: {act.type}, Акция: {act.share.ticker}, Кол-во: {act.quantity}"
                    for act in success_action_list
                ])
                if len(error_action_list) > 0:
                    error_message = "Ошибки:\n" + "\n".join( [
                        f"При выполнении действия с {error.data.share.ticker} ошибка: {error.description}"
                        for error in error_action_list
                    ])
                    message = f"{message}\n{error_message}"
            else:  # get_callable_bonds
                callable_bonds = data.get("callable_bonds")
                message = head + "Тикер - Название - Дата оферты\n" + "\n".join( [
                    f"{_bond.ticker} - {_bond.figi} - {_bond.offer_date} "
                    for _bond in callable_bonds
                ])

            return await self.bot.send_message(chat_id, message)

        return None

    async def _rebalance(self, user):

            account_id = user.index_bindings.broker_account_id

            manager = PortfolioManager(account_id)
            portfolio = manager.get_portfolio()

            balance_before_balance = portfolio.cash.to_float()
            if balance_before_balance > settings.balancer.max_cash:
                index_moex = manager.get_index_list(user.index_bindings.index_name)
                actions, new_balance = manager.get_action_for_rebalance(portfolio, index_moex)  # Для обновления списка действий
                success_action_list, error_action_list = manager.execute_actions()

                await self._send_report(user.telegram_id, "rebalance",
                                        success_action_list=success_action_list,
                                        error_action_list=error_action_list)
                _save_result(success_action_list)
                _save_result(error_action_list)

                ConfigLoader.update_schedule(user.telegram_id, user.schedule.rebalance_frequency)

            await asyncio.sleep(settings.scheduler.timeout_in_sec)

    async def _get_callable_bonds(self, telegram_id, broker_account_id):

        manager = PortfolioManager(broker_account_id)
        now = datetime.now()
        callable_bonds = [ _bond for _bond in manager.get_callable_bonds()
                           if datetime.strptime(_bond.offer_date, "%Y-%m-%d") - now <= timedelta(weeks=2)
                        ]
        if callable_bonds:
            results = await self._send_report(telegram_id, "get_callable_bonds", callable_bonds=callable_bonds)
            if isinstance(results, Message):
                results = results.model_dump_json()
            _save_result(callable_bonds)
        else:
            results = "No suitable bonds were found"

        return results


    async def run(self):

        def should_rebalance(last_run: datetime = None, frequency: str = None) -> bool:
            if last_run and frequency:
                now = datetime.now()
                if frequency == ScheduleFrequency.WEEKLY.name:
                    return now - last_run >= timedelta(weeks=1)
                elif frequency == ScheduleFrequency.MONTHLY.name:
                    return now - last_run >= timedelta(days=30) # Пока по-простому, в будущем переделаем
                elif frequency == ScheduleFrequency.QUARTERLY.name:
                    return (now.month - 1) // 3 != (last_run.month - 1) // 3 or now.year != last_run.year
                else:
                    return False
            else:
                return False

        while True:
            for user in settings.users:
                if user.schedule:
                    if should_rebalance(user.schedule.last_run, user.schedule.rebalance_frequency):
                        await self._rebalance(user)

            async for session in get_session():
                repo = TaskRepository(session)
                tasks = await repo.get_tasks()

                for task in tasks:
                    if not task.disabled_date:
                        try:
                            if should_rebalance(task.last_checked_date, task.frequency.name):
                                if task.task_type == TaskType.BOND_EVENTS_MONITOR:
                                    if not task.params:
                                        await repo.save_result(
                                            task.id,
                                            result="failed",
                                            errors=f"Don't have params for {task.task_type}"
                                        )
                                    else:
                                        broker_account_id = task.params.get("broker_account_id")
                                        result = await self._get_callable_bonds(task.user.telegram_id, broker_account_id)
                                        if result:
                                            await repo.save_result(
                                                task.id,
                                                result=result
                                            )
                                        else:
                                            await repo.save_result(
                                                task.id,
                                                result="failed",
                                                errors=f"Method send report return 'None' result"
                                            )

                        except Exception as e:

                            logger.exception("Task failed")

                            await repo.save_result(
                                task.id,
                                result="failed",
                                errors=str(e)
                            )

            await asyncio.sleep(settings.scheduler.timeout_in_sec)

if __name__ == "__main__":
    async def scheduler_loop():
        telegram_token = settings.telegram.token
        bot = Bot(token=telegram_token)
        scheduler = Scheduler(bot)

        while True:
            await scheduler.run()
            await asyncio.sleep(settings.scheduler.timeout_in_sec)

    async def create_test_task():


        async for session in get_session():
            repo = TaskRepository(session)
            user_repo = UserRepository(session)

            user = await user_repo.get_user_by_telegram_id(190741373)
            if user:
                await repo.create_task(
                    task_type=TaskType.BOND_EVENTS_MONITOR,
                    frequency=ScheduleFrequency.WEEKLY,
                    user=user

                )

    # asyncio.run(create_test_task())
    # asyncio.run(scheduler_loop())