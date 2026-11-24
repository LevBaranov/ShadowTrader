"""Планировщик: исполнение задач из таблицы task.

Работает только по БД (никакого toml-списка пользователей):
- REBALANCE: балансировка портфеля по стратегии, если накопился свободный кэш;
- BOND_EVENTS_MONITOR: облигации с офертой/колл-опционом в ближайшие 2 недели;
- INDEX_SYNC: системная задача без владельца — ежедневно обновляет составы
  индексов, на которые есть стратегии;
- MOEX_BONDS_SYNC: системная задача — ежедневно обновляет справочник облигаций
  MOEX, заодно подтягивая даты подачи заявок на оферту из bondization;
- MOEX_BONDS_OFFER_DATE_SYNC: системная задача — сверяет bondization со
  справочником и раздаёт владельцам BOND_EVENTS_MONITOR разовые задачи
  NOTIFY_START_OFFER_DATE по новым датам подачи заявок, чтобы не ждать
  недельного цикла монитора;
- NOTIFY_START_OFFER_DATE: разовая задача пользователя — проверяет позиции
  счёта по списку бумаг, шлёт уведомление и отключается.

Уведомления — через NotificationService (Telegram/почта по identities пользователя).
"""
import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Callable

from src.core.crypto import decrypt_token
from src.core.index_sync_service import IndexSyncService
from src.core.bond_cache_service import MoexBondCacheService
from src.core.instrument_service import InstrumentService
from src.core.user_service import build_portfolio_manager_for_account
from src.core.verification import utcnow
from src.db.enums import TaskType
from src.db.models.task import Task
from src.db.repositories.brokers_account_repository import BrokersAccountRepository
from src.db.repositories.moex_bond_repository import MoexBondsRepository
from src.db.repositories.task_repository import TaskRepository
from src.db.repositories.users_strategy_repository import UsersStrategyRepository
from src.models.balancer_params import BalancerParams
from src.models.scheduler_frequency import ScheduleFrequency
from src.scheduler import reports

logger = logging.getLogger(__name__)

# За сколько до события предупреждаем владельца бумаги.
BOND_EVENTS_HORIZON = timedelta(weeks=2)
# Оферты раньше этой даты уже прошли — в bondization не запрашиваем.
OFFERS_LOOKBACK = timedelta(days=2)


def should_run(last_run: datetime | None, frequency: ScheduleFrequency | None) -> bool:
    """Пора ли выполнять задачу (перенесено из старого планировщика как есть)."""
    if not last_run or not frequency:
        return False

    now = utcnow()
    if frequency == ScheduleFrequency.DAILY:
        return now - last_run >= timedelta(days=1)
    if frequency == ScheduleFrequency.WEEKLY:
        return now - last_run >= timedelta(weeks=1)
    if frequency == ScheduleFrequency.MONTHLY:
        return now - last_run >= timedelta(days=30)  # Пока по-простому, в будущем переделаем
    if frequency == ScheduleFrequency.QUARTERLY:
        return (now.month - 1) // 3 != (last_run.month - 1) // 3 or now.year != last_run.year
    return False


class SchedulerRunner:

    def __init__(self, session_factory, notifications, portfolio_manager_factory: Callable,
                 index_sync: IndexSyncService | None = None,
                 instrument_service: InstrumentService | None = None):
        self.session_factory = session_factory
        self.notifications = notifications
        self.portfolio_manager_factory = portfolio_manager_factory
        self.index_sync = index_sync if index_sync is not None else IndexSyncService()
        self.instrument_service = (
            instrument_service if instrument_service is not None else InstrumentService()
        )

    async def run_once(self) -> None:
        async with self.session_factory() as session:
            task_repo = TaskRepository(session)
            strategy_repo = UsersStrategyRepository(session)
            account_repo = BrokersAccountRepository(session)

            for task in await task_repo.get_active_tasks():
                if not should_run(task.last_checked_date, task.frequency):
                    continue

                try:
                    result = await self._execute(task, strategy_repo, account_repo, session)
                    logger.info("Task %s (%s) done: %s", task.id, task.task_type, result)
                    await task_repo.save_result(task.id, result=result)
                except Exception as error:
                    logger.exception("Task %s failed", task.id)
                    await task_repo.save_result(task.id, result="failed", errors=str(error))

    async def _execute(self, task: Task, strategy_repo, account_repo, session=None) -> str:
        if task.task_type == TaskType.REBALANCE:
            return await self._run_rebalance(task, strategy_repo, session)
        if task.task_type == TaskType.BOND_EVENTS_MONITOR:
            return await self._run_bond_monitor(task, account_repo, session)
        if task.task_type == TaskType.MOEX_BONDS_SYNC:
            return await self._run_moex_bonds_sync(session)
        if task.task_type == TaskType.MOEX_BONDS_OFFER_DATE_SYNC:
            if session is None:
                raise ValueError("MOEX_BONDS_OFFER_DATE_SYNC task requires a session")
            return await self._run_offers_date_sync(session)
        if task.task_type == TaskType.NOTIFY_START_OFFER_DATE:
            return await self._run_offers_notification(task, account_repo, session)
        if task.task_type == TaskType.INDEX_SYNC:
            if session is None:
                raise ValueError("INDEX_SYNC task requires a session")
            return await self._run_index_sync(session)
        raise ValueError(f"Unknown task type: {task.task_type}")

    async def _run_rebalance(self, task: Task, strategy_repo, session) -> str:
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
        # Состав индекса — из БД (при отсутствии разово с биржи), мета инструментов —
        # из справочника (при протухании inline-refresh токеном владельца счёта).
        composition = await self.index_sync.ensure_composition(
            session, strategy.stock_markets_index
        )
        users_broker = strategy.brokers_account.users_broker
        directory = await self.instrument_service.ensure_directory(
            session,
            decrypt_token(users_broker.broker_token),
            users_broker.sandbox,
            must_contain=composition.tickers,
        )

        def _calculate() :
            return manager.calculate_rebalance(index_name, params, composition, directory=directory)

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

    async def _run_index_sync(self, session) -> str:
        """Системная задача: обновить составы индексов, на которые есть стратегии."""
        return await self.index_sync.sync_strategy_indices(session)

    async def _run_bond_monitor(self, task: Task, account_repo, session=None) -> str:
        account_id = uuid.UUID((task.params or {})["brokers_account_id"])
        account = await account_repo.get_for_user(account_id, task.user_id)
        if account is None:
            raise ValueError(f"Account {account_id} not found for user {task.user_id}")

        manager = build_portfolio_manager_for_account(account, self.portfolio_manager_factory)
        if session is None:
            directory = None
        else:
            users_broker = account.users_broker
            directory = await self.instrument_service.ensure_directory(
                session,
                decrypt_token(users_broker.broker_token),
                users_broker.sandbox,
            )
        if session is None:
            moex_bonds = None
        else:
            moex_bonds = await MoexBondCacheService().get_bonds(session)

        # Поход к брокеру/MOEX синхронный — уводим в тред.
        bonds = await asyncio.to_thread(
            manager.get_bonds_with_events, directory=directory, moex_bonds=moex_bonds
        )

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

    async def _run_moex_bonds_sync(self, session) -> str:
        """Системная задача: обновить справочник облигаций MOEX."""
        if session is None:
            raise ValueError("MOEX_BONDS_SYNC task requires a session")
        sync_service = MoexBondCacheService()
        count = await sync_service.refresh(session)
        return f"synced: {count} moex bonds"

    async def _run_offers_date_sync(self, session) -> str:
        """Системная задача: сверить bondization со справочником и раздача задач.

        Дата подачи заявок, отличающаяся от сохранённой в справочнике (или
        узнанная впервые), — «новая». По каждой новой дате владельцу активного
        BOND_EVENTS_MONITOR создаём разовую NOTIFY_START_OFFER_DATE. Если такая
        задача у владельца ещё не исполнена — новую не создаём.
        """
        from_date = date.today() - OFFERS_LOOKBACK
        offers = await asyncio.to_thread(MoexBondCacheService().moex.get_bond_offers, from_date)

        bonds_repo = MoexBondsRepository(session)
        new_offers = await bonds_repo.known_offer_start_dates(offers)
        if not new_offers:
            return "no new offer start dates"

        task_repo = TaskRepository(session)
        monitors = await task_repo.get_active_tasks_by_type(TaskType.BOND_EVENTS_MONITOR)
        created = 0
        for monitor in monitors:
            account_id = (monitor.params or {}).get("brokers_account_id")
            if not account_id:
                continue

            existing = await task_repo.get_user_tasks(
                monitor.user_id, brokers_account_id=account_id
            )
            if any(task.task_type == TaskType.NOTIFY_START_OFFER_DATE for task in existing):
                continue

            await task_repo.create_task(
                task_type=TaskType.NOTIFY_START_OFFER_DATE,
                frequency=ScheduleFrequency.DAILY,
                user=monitor.user,
                params={"brokers_account_id": account_id},
                last_checked_date=datetime(2000, 1, 1),
            )
            created += 1

        # Даты сохранены: на следующем проходе они уже не «новые»,
        # а пропущенные бумаги в любом случае догонит BOND_EVENTS_MONITOR.
        await bonds_repo.update_offer_start_dates(new_offers)
        return f"created {created} tasks for {len(new_offers)} bonds"

    async def _run_offers_notification(self, task: Task, account_repo, session=None) -> str:
        """Разовая задача пользователя: уведомить о датах подачи заявок на оферту.

        Исполняется в ближайшем цикле планировщика, после чего отключается —
        следующий проход её пропустит. Даты берём из справочника moex_bonds,
        поэтому сверять с params не нужно.
        """
        account_id = uuid.UUID((task.params or {})["brokers_account_id"])
        task_repo = TaskRepository(session) if session is not None else None
        try:
            account = await account_repo.get_for_user(account_id, task.user_id)
            if account is None:
                # Постоянная ошибка (чужой/несуществующий счёт): повторять
                # бессмысленно — закрываем задачу и пробрасываем ошибку.
                if task_repo is not None:
                    await task_repo.disable_task(task.id)
                raise ValueError(f"Account {account_id} not found for user {task.user_id}")

            manager = build_portfolio_manager_for_account(account, self.portfolio_manager_factory)
            if session is None:
                directory = None
            else:
                users_broker = account.users_broker
                directory = await self.instrument_service.ensure_directory(
                    session,
                    decrypt_token(users_broker.broker_token),
                    users_broker.sandbox,
                )
            if session is None:
                moex_bonds = None
            else:
                moex_bonds = await MoexBondCacheService().get_bonds(session)

            bonds = await asyncio.to_thread(
                manager.get_bonds_with_events, directory=directory, moex_bonds=moex_bonds
            )

            deadline = date.today() + BOND_EVENTS_HORIZON
            soon = []
            for bond in bonds:
                events = [
                    event for event in bond.events
                    if event.date <= deadline
                    and event.type.name == "OFFER_START"
                ]
                if events:
                    soon.append((bond, events))

            if soon:
                await self.notifications.notify(
                    task.user,
                    subject="ShadowTrader: открылась подача заявок на оферту",
                    text=reports.bonds_report(soon),
                )
                notified = f"notified about {len(soon)} bonds"
            else:
                notified = "no suitable bonds were found"
        except Exception:
            # Временную ошибку не глотаем и задачу не отключаем — повторим.
            logger.exception("Offer notification failed for task %s", task.id)
            raise

        if task_repo is not None:
            await task_repo.disable_task(task.id)
        return notified


async def ensure_moex_bonds_sync_task(session_factory) -> None:
    """Создать системную задачу MOEX_BONDS_SYNC, если её ещё нет."""
    async with session_factory() as session:
        task_repo = TaskRepository(session)
        existing = await task_repo.get_active_system_task(TaskType.MOEX_BONDS_SYNC)
        if existing is not None:
            return
        await task_repo.create_task(
            task_type=TaskType.MOEX_BONDS_SYNC,
            frequency=ScheduleFrequency.DAILY,
            user=None,
            params={},
            last_checked_date=datetime(2000, 1, 1),
        )
        logger.info("Created system task MOEX_BONDS_SYNC")


async def ensure_bonds_offer_date_sync_task(session_factory) -> None:
    """Создать системную задачу MOEX_BONDS_OFFER_DATE_SYNC, если её ещё нет."""
    async with session_factory() as session:
        task_repo = TaskRepository(session)
        existing = await task_repo.get_active_system_task(TaskType.MOEX_BONDS_OFFER_DATE_SYNC)
        if existing is not None:
            return
        await task_repo.create_task(
            task_type=TaskType.MOEX_BONDS_OFFER_DATE_SYNC,
            frequency=ScheduleFrequency.DAILY,
            user=None,
            params={},
            last_checked_date=datetime(2000, 1, 1),
        )
        logger.info("Created system task MOEX_BONDS_OFFER_DATE_SYNC")


async def ensure_index_sync_task(session_factory) -> None:
    """Создать системную задачу INDEX_SYNC, если её ещё нет.

    Идемпотентно: вызывается при каждом старте планировщика. Новую задачу
    датируем прошлым, чтобы первый проход выполнил синк сразу и стратегии
    получили составы без ожидания суток.
    """
    async with session_factory() as session:
        task_repo = TaskRepository(session)
        existing = await task_repo.get_active_system_task(TaskType.INDEX_SYNC)
        if existing is not None:
            return
        await task_repo.create_task(
            task_type=TaskType.INDEX_SYNC,
            frequency=ScheduleFrequency.DAILY,
            user=None,
            params={},
            last_checked_date=datetime(2000, 1, 1),
        )
        logger.info("Created system task INDEX_SYNC")
