import os
from datetime import datetime, timedelta
import asyncio

from aiogram import Bot

from src.core.portfolio_manager import PortfolioManager
from src.config import settings, ConfigLoader

from src.models.scheduler_frequency import ScheduleFrequency


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


class Scheduler:


    def __init__(self, bot: Bot = None):

        self.bot = bot

    async def _send_report(self, chat_id, success_action_list, error_action_list):

        if self.bot:

            head = "Я тут немного 'пошуршал' пока ты не видел.\n"
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

                await self._send_report(user.telegram_id, success_action_list, error_action_list)
                _save_result(success_action_list)
                _save_result(error_action_list)

                ConfigLoader.update_schedule(user.telegram_id, user.schedule.rebalance_frequency)

            await asyncio.sleep(settings.scheduler.timeout_in_sec)


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
                if user.schedule and should_rebalance(user.schedule.last_run, user.schedule.rebalance_frequency):
                    await self._rebalance(user)

            await asyncio.sleep(settings.scheduler.timeout_in_sec)
