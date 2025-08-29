import os
from datetime import datetime, timedelta
import asyncio

from src.core.portfolio_manager import PortfolioManager
from src.config import settings, ConfigLoader

from src.models.scheduler_frequency import ScheduleFrequency


class Scheduler:

    async def rebalance_scheduler(self):

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

        def save_result(obj: list):
            if not obj:
                return

            obj_type = type(obj[0]).__name__
            filename = f"{obj_type}s.txt"

            os.makedirs('../scheduler_results', exist_ok=True)

            filepath = os.path.join('../scheduler_results', filename)

            with open(filepath, 'a', encoding='utf-8') as f:
                for item in obj:
                    f.write(f"[{datetime.now()}] {str(item)}\n")

        while True:
            for user in settings.users:

                if user.schedule and should_rebalance(user.schedule.last_run, user.schedule.rebalance_frequency):
                    account_id = user.links.broker_account_id

                    manager = PortfolioManager(account_id)
                    portfolio = manager.get_portfolio()

                    balance_before_balance = portfolio.cash.to_float()
                    if balance_before_balance > settings.balancer.max_cash:
                        print("Bingo")
                        index_moex = manager.get_index_list(user.links.index_name)
                        actions, new_balance = manager.get_action_for_rebalance(portfolio, index_moex)  # Для обновления списка действий
                        #TODO: Сделать уведомления о действиях выполненных по расписанию
                        success_action_list, error_action_list = manager.execute_actions()
                        save_result(success_action_list)
                        save_result(error_action_list)
                        ConfigLoader.update_schedule(user.telegram_id, user.schedule.rebalance_frequency)

            await asyncio.sleep(settings.scheduler.timeout_in_sec)