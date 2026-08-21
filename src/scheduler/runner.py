"""Планировщик: исполнение задач из таблицы task.

Работает только по БД (никакого toml-списка пользователей):
- REBALANCE: балансировка портфеля по стратегии, если накопился свободный кэш;
- BOND_EVENTS_MONITOR: облигации с офертой/колл-опционом в ближайшие 2 недели.

Уведомления — через NotificationService (Telegram/почта по identities пользователя).
"""
import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta

from src.core.user_service import build_portfolio_manager_for_account
from src.db.enums import TaskType
from src.db.models.task import Task
from src.db.repositories.brokers_account_repository import BrokersAccountRepository
from src.db.repositories.task_repository import TaskRepository
from src.db.repositories.users_strategy_repository import UsersStrategyRepository
from src.models.balancer_params import BalancerParams
from src.models.scheduler_frequency import ScheduleFrequency
from src.scheduler import reports

logger = logging.getLogger(__name__)

# За сколько до события предупреждаем владельца бумаги.
BOND_EVENTS_HORIZON = timedelta(weeks=2)


def should_run(last_run: datetime | None, frequency: ScheduleFrequency | None) -> bool:
    """Пора ли выполнять задачу (перенесено из старого планировщика как есть)."""
    if not last_run or not frequency:
        return False

    now = datetime.now()
    if frequency == ScheduleFrequency.WEEKLY:
        return now - last_run >= timedelta(weeks=1)
    if frequency == ScheduleFrequency.MONTHLY:
        return now - last_run >= timedelta(days=30)  # Пока по-простому, в будущем переделаем
    if frequency == ScheduleFrequency.QUARTERLY:
        return (now.month - 1) // 3 != (last_run.month - 1) // 3 or now.year != last_run.year
    return False


class SchedulerRunner:

    def __init__(self, session_factory, notifications, portfolio_manager_factory):
        self.session_factory = session_factory
        self.notifications = notifications
        self.portfolio_manager_factory = portfolio_manager_factory

    async def run_once(self) -> None:
        async with self.session_factory() as session:
            task_repo = TaskRepository(session)
            strategy_repo = UsersStrategyRepository(session)
            account_repo = BrokersAccountRepository(session)

            for task in await task_repo.get_active_tasks():
                if not should_run(task.last_checked_date, task.frequency):
                    continue

                try:
                    result = await self._execute(task, strategy_repo, account_repo)
                    logger.info("Task %s (%s) done: %s", task.id, task.task_type, result)
                    await task_repo.save_result(task.id, result=result)
                except Exception as error:
                    logger.exception("Task %s failed", task.id)
                    await task_repo.save_result(task.id, result="failed", errors=str(error))

    async def _execute(self, task: Task, strategy_repo, account_repo) -> str:
        if task.task_type == TaskType.REBALANCE:
            return await self._run_rebalance(task, strategy_repo)
        if task.task_type == TaskType.BOND_EVENTS_MONITOR:
            return await self._run_bond_monitor(task, account_repo)
        raise ValueError(f"Unknown task type: {task.task_type}")

    async def _run_rebalance(self, task: Task, strategy_repo) -> str:
        strategy_id = uuid.UUID((task.params or {})["strategy_id"])
        # Владельца проверяем здесь: задача исполняется только над стратегией её автора.
        strategy = await strategy_repo.get_user_strategy(task.user_id, strategy_id)
        if strategy is None:
            raise ValueError(f"Strategy {strategy_id} not found for user {task.user_id}")
        if strategy.brokers_account.deleted_at is not None:
            raise ValueError(f"Account of strategy {strategy_id} is deleted")

        index_name = strategy.stock_markets_index.index_name
        manager = build_portfolio_manager_for_account(
            strategy.brokers_account, self.portfolio_manager_factory
        )

        # Параметры расчёта — настройки пользователя: комиссия с брокера счёта,
        # delta / min_lots_to_keep / max_cash со стратегии.
        params = BalancerParams.from_strategy(strategy)

        def _calculate() :
            return manager.calculate_rebalance(index_name, params)

        preview = await asyncio.to_thread(_calculate)

        # Порог запуска — настройка задачи (params.min_free_cash), а не стратегии:
        # балансируем только когда накопился ощутимый свободный кэш.
        min_free_cash = (task.params or {}).get("min_free_cash") or 0
        if preview.current_free_cash <= min_free_cash:
            return "skipped: free cash below threshold"

        success_actions, error_actions = await asyncio.to_thread(manager.execute_actions)

        await self.notifications.notify(
            task.user,
            subject="ShadowTrader: балансировка выполнена",
            text=reports.rebalance_report(success_actions, error_actions),
        )

        return f"executed: {len(success_actions)} actions, {len(error_actions)} errors"

    async def _run_bond_monitor(self, task: Task, account_repo) -> str:
        account_id = uuid.UUID((task.params or {})["brokers_account_id"])
        account = await account_repo.get_for_user(account_id, task.user_id)
        if account is None:
            raise ValueError(f"Account {account_id} not found for user {task.user_id}")

        manager = build_portfolio_manager_for_account(account, self.portfolio_manager_factory)
        bonds = await asyncio.to_thread(manager.get_bonds_with_events)

        # Пользователя дёргаем только когда событие уже на горизонте: остальные
        # бумаги он видит сам в разделе облигаций.
        deadline = date.today() + BOND_EVENTS_HORIZON
        soon = []
        for bond in bonds:
            events = [event for event in bond.events if event.date <= deadline]
            if events:
                soon.append((bond, events))

        if not soon:
            return "no suitable bonds were found"

        await self.notifications.notify(
            task.user,
            subject="ShadowTrader: скоро событие по облигациям",
            text=reports.bonds_report(soon),
        )

        return f"notified about {len(soon)} bonds"
