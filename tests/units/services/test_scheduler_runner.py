"""Тесты планировщика: should_run и обработка задач с fake-сервисами."""
import asyncio
import uuid
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.core.verification import utcnow
from src.db.enums import TaskType
from src.models.bond import BondEvent, BondEventType
from src.models.index_composition import CompositionSnapshot
from src.models.scheduler_frequency import ScheduleFrequency
from src.scheduler.runner import SchedulerRunner, ensure_index_sync_task, should_run


class TestShouldRun:

    def test_daily(self):
        assert should_run(utcnow() - timedelta(hours=25), ScheduleFrequency.DAILY)
        assert not should_run(utcnow() - timedelta(hours=12), ScheduleFrequency.DAILY)

    def test_weekly(self):
        assert should_run(utcnow() - timedelta(days=8), ScheduleFrequency.WEEKLY)
        assert not should_run(utcnow() - timedelta(days=2), ScheduleFrequency.WEEKLY)

    def test_monthly(self):
        assert should_run(utcnow() - timedelta(days=31), ScheduleFrequency.MONTHLY)
        assert not should_run(utcnow() - timedelta(days=10), ScheduleFrequency.MONTHLY)

    def test_quarterly_same_quarter(self):
        now = utcnow()
        assert not should_run(now - timedelta(days=1), ScheduleFrequency.QUARTERLY) or (
            (now.month - 1) // 3 != ((now - timedelta(days=1)).month - 1) // 3
        )

    def test_none_values(self):
        assert not should_run(None, ScheduleFrequency.WEEKLY)
        assert not should_run(utcnow(), None)


class FakeNotifications:
    def __init__(self):
        self.sent = []

    async def notify(self, user, subject, text):
        self.sent.append((user, subject, text))


class FakeStrategyRepo:
    def __init__(self, strategy=None):
        self.strategy = strategy

    async def get_user_strategy(self, user_id, strategy_id):
        if self.strategy and self.strategy.user_id == user_id and self.strategy.id == strategy_id:
            return self.strategy
        return None


class FakeAccountRepo:
    def __init__(self, account=None, owner_id=None):
        self.account = account
        self.owner_id = owner_id

    async def get_for_user(self, account_pk, user_id):
        if self.account is not None and user_id == self.owner_id:
            return self.account
        return None


def make_share(ticker):
    return SimpleNamespace(ticker=ticker)


class FakeInstrumentService:
    def __init__(self, directory=None):
        self.directory = directory

    async def ensure_directory(self, session, token, sandbox, must_contain=frozenset()):
        from src.models.instrument_directory import InstrumentDirectory
        return self.directory or InstrumentDirectory(sandbox=sandbox, updated_at=None)


class FakeIndexSync:
    """Состав индекса без БД и биржи."""

    def __init__(self, snapshot=None, sync_result="synced: 1 indices"):
        self.snapshot = snapshot
        self.sync_result = sync_result
        self.synced_sessions = []

    async def ensure_composition(self, session, index_row):
        return self.snapshot or CompositionSnapshot(
            index_name="IMOEX", tradedate=date.today(), rows=[]
        )

    async def sync_strategy_indices(self, session):
        self.synced_sessions.append(session)
        return self.sync_result


class FakeManager:
    def __init__(self, free_cash=100000.0, bonds=None):
        self.free_cash = free_cash
        self.bonds = bonds or []
        self.executed = False
        # Чем расчёт параметризовали — проверяем, что настройка стратегии доехала.
        self.calculated_with = None

    def calculate_rebalance(self, index_name, params, composition=None, directory=None):
        self.calculated_with = (index_name, params, composition, directory)
        return SimpleNamespace(current_free_cash=self.free_cash, free_cash=10.0, positions=[], actions=[])

    def execute_actions(self):
        self.executed = True
        action = SimpleNamespace(type="BUY", quantity=2, share=make_share("SBER"))
        return [action], []

    def get_bonds_with_events(self, account_id=None, since=None, directory=None, moex_bonds=None):
        return self.bonds


@pytest.fixture
def user():
    identity = SimpleNamespace(provider="TELEGRAM", external_id="123456789")
    return SimpleNamespace(id=uuid.uuid4(), telegram_id=123456789, email=None)


def make_strategy(user, max_cash=0, commission="0.003"):
    """Стратегия так, как её видит планировщик: с настройками расчёта и брокером счёта."""
    from src.core.crypto import encrypt_token
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user.id,
        max_cash=max_cash,
        delta=Decimal("0.05"),
        min_lots_to_keep=1,
        brokers_account=SimpleNamespace(
            deleted_at=None,
            users_broker=SimpleNamespace(
                commission=Decimal(commission),
                broker_token=encrypt_token("t.token"),
                sandbox=False,
            ),
        ),
        stock_markets_index=SimpleNamespace(index_name="IMOEX"),
    )


def make_task(user, task_type, params):
    return SimpleNamespace(
        id=uuid.uuid4(),
        task_type=task_type,
        frequency=ScheduleFrequency.WEEKLY,
        user_id=user.id,
        user=user,
        params=params,
        last_checked_date=utcnow() - timedelta(days=10),
        disabled_date=None,
    )


@pytest.fixture
def notifications():
    return FakeNotifications()


def make_runner(notifications, manager, monkeypatch, index_sync=None, instrument_service=None):
    runner = SchedulerRunner(
        session_factory=None,
        notifications=notifications,
        portfolio_manager_factory=None,
        index_sync=index_sync or FakeIndexSync(),
        instrument_service=instrument_service or FakeInstrumentService(),
    )
    monkeypatch.setattr(
        "src.scheduler.runner.build_portfolio_manager_for_account",
        lambda account, factory: manager,
    )
    return runner


class TestRebalanceTask:

    def test_executes_and_notifies_when_cash_above_threshold(self, user, notifications, monkeypatch):
        manager = FakeManager(free_cash=100000.0)
        runner = make_runner(notifications, manager, monkeypatch)
        strategy = make_strategy(user)
        task = make_task(
            user, TaskType.REBALANCE,
            {"strategy_id": str(strategy.id), "min_free_cash": 2000},
        )

        result = asyncio.run(runner._execute(task, FakeStrategyRepo(strategy), FakeAccountRepo()))

        assert manager.executed
        assert result == "executed: 1 actions, 0 errors"
        assert len(notifications.sent) == 1
        assert "SBER" in notifications.sent[0][2]

    def test_skips_when_cash_below_threshold(self, user, notifications, monkeypatch):
        manager = FakeManager(free_cash=100.0)
        runner = make_runner(notifications, manager, monkeypatch)
        strategy = make_strategy(user)
        task = make_task(
            user, TaskType.REBALANCE,
            {"strategy_id": str(strategy.id), "min_free_cash": 2000},
        )

        result = asyncio.run(runner._execute(task, FakeStrategyRepo(strategy), FakeAccountRepo()))

        assert not manager.executed
        assert result.startswith("skipped")
        assert notifications.sent == []

    def test_threshold_comes_from_task_params(self, user, notifications, monkeypatch):
        """Порог задаёт задача: тот же кэш при меньшем пороге уже балансируется."""
        manager = FakeManager(free_cash=3000.0)
        runner = make_runner(notifications, manager, monkeypatch)
        strategy = make_strategy(user)
        task = make_task(
            user, TaskType.REBALANCE,
            {"strategy_id": str(strategy.id), "min_free_cash": 1000},
        )

        result = asyncio.run(runner._execute(task, FakeStrategyRepo(strategy), FakeAccountRepo()))

        assert manager.executed
        assert result.startswith("executed")

    def test_missing_threshold_means_no_threshold(self, user, notifications, monkeypatch):
        """Задача без min_free_cash (создана до миграции) балансируется на любом кэше."""
        manager = FakeManager(free_cash=1.0)
        runner = make_runner(notifications, manager, monkeypatch)
        strategy = make_strategy(user)
        task = make_task(user, TaskType.REBALANCE, {"strategy_id": str(strategy.id)})

        result = asyncio.run(runner._execute(task, FakeStrategyRepo(strategy), FakeAccountRepo()))

        assert manager.executed

    def test_user_settings_go_to_calculation(self, user, notifications, monkeypatch):
        """Настройки расчёта — из БД: max_cash со стратегии, комиссия с брокера счёта."""
        manager = FakeManager(free_cash=100000.0)
        runner = make_runner(notifications, manager, monkeypatch)
        strategy = make_strategy(user, max_cash=15000, commission="0.01")
        task = make_task(
            user, TaskType.REBALANCE,
            {"strategy_id": str(strategy.id), "min_free_cash": 2000},
        )

        asyncio.run(runner._execute(task, FakeStrategyRepo(strategy), FakeAccountRepo()))

        index_name, params, _composition, _directory = manager.calculated_with
        assert index_name == "IMOEX"
        assert params.max_cash == 15000
        assert params.commission == Decimal("0.01")
        assert params.delta == Decimal("0.05")
        assert params.min_lots_to_keep == 1

    def test_foreign_strategy_raises(self, user, notifications, monkeypatch):
        manager = FakeManager()
        runner = make_runner(notifications, manager, monkeypatch)
        task = make_task(user, TaskType.REBALANCE, {"strategy_id": str(uuid.uuid4())})

        with pytest.raises(ValueError):
            asyncio.run(runner._execute(task, FakeStrategyRepo(None), FakeAccountRepo()))


def make_system_task(task_type):
    return SimpleNamespace(
        id=uuid.uuid4(),
        task_type=task_type,
        frequency=ScheduleFrequency.DAILY,
        user_id=None,
        user=None,
        params={},
        last_checked_date=utcnow() - timedelta(days=2),
        disabled_date=None,
    )


class TestIndexSyncTask:

    def test_runs_sync_and_returns_result(self, notifications, monkeypatch):
        index_sync = FakeIndexSync(sync_result="synced: 2 indices")
        runner = make_runner(notifications, FakeManager(), monkeypatch, index_sync=index_sync)
        task = make_system_task(TaskType.INDEX_SYNC)

        result = asyncio.run(runner._execute(task, FakeStrategyRepo(), FakeAccountRepo(), session="session"))

        assert result == "synced: 2 indices"
        assert index_sync.synced_sessions == ["session"]

    def test_requires_session(self, notifications, monkeypatch):
        runner = make_runner(notifications, FakeManager(), monkeypatch)
        task = make_system_task(TaskType.INDEX_SYNC)

        with pytest.raises(ValueError):
            asyncio.run(runner._execute(task, FakeStrategyRepo(), FakeAccountRepo()))

    def test_rebalance_gets_composition(self, user, notifications, monkeypatch):
        """Состав доезжает до расчёта третьим аргументом."""
        from src.models.index_composition import CompositionRow
        snapshot = CompositionSnapshot(
            index_name="IMOEX",
            tradedate=date.today(),
            rows=[CompositionRow(ticker="SBER", shortname="Сбер", weight=14.0)],
        )
        manager = FakeManager(free_cash=100000.0)
        runner = make_runner(
            notifications, manager, monkeypatch, index_sync=FakeIndexSync(snapshot=snapshot)
        )
        strategy = make_strategy(user)
        task = make_task(
            user, TaskType.REBALANCE,
            {"strategy_id": str(strategy.id), "min_free_cash": 2000},
        )

        asyncio.run(runner._execute(task, FakeStrategyRepo(strategy), FakeAccountRepo()))

        assert manager.calculated_with[2] is snapshot


class FakeTaskRepo:
    def __init__(self, existing=None):
        self.existing = existing
        self.created = []

    async def get_active_system_task(self, task_type):
        return self.existing

    async def create_task(self, task_type, frequency, user, params, last_checked_date):
        self.created.append((task_type, frequency, user, params, last_checked_date))
        return SimpleNamespace(id=uuid.uuid4())


class TestEnsureIndexSyncTask:

    def test_creates_when_missing(self, monkeypatch):
        import src.scheduler.runner as runner_module
        repo = FakeTaskRepo(existing=None)
        monkeypatch.setattr(runner_module, "TaskRepository", lambda session: repo)

        # session_factory вызывается как session_factory() -> async CM
        def session_factory():
            class Session:
                async def __aenter__(self):
                    return "session"

                async def __aexit__(self, *args):
                    return False
            return Session()

        asyncio.run(ensure_index_sync_task(session_factory))

        assert len(repo.created) == 1
        task_type, frequency, user, params, last_checked = repo.created[0]
        assert task_type == TaskType.INDEX_SYNC
        assert frequency == ScheduleFrequency.DAILY
        assert user is None
        assert last_checked < utcnow() - timedelta(days=30)

    def test_skips_when_exists(self, monkeypatch):
        import src.scheduler.runner as runner_module
        repo = FakeTaskRepo(existing=SimpleNamespace(id=uuid.uuid4()))
        monkeypatch.setattr(runner_module, "TaskRepository", lambda session: repo)

        def session_factory():
            class Session:
                async def __aenter__(self):
                    return "session"

                async def __aexit__(self, *args):
                    return False
            return Session()

        asyncio.run(ensure_index_sync_task(session_factory))

        assert repo.created == []


def make_bond(ticker, *events, short_name=None):
    """Облигация с предстоящими событиями — как её отдаёт PortfolioManager."""
    return SimpleNamespace(
        ticker=ticker,
        short_name=short_name,
        events=[BondEvent(type=event_type, date=event_date) for event_type, event_date in events],
    )


class TestBondMonitorTask:

    def test_notifies_about_events_on_horizon(self, user, notifications, monkeypatch):
        soon = date.today() + timedelta(days=3)
        far = date.today() + timedelta(days=60)
        manager = FakeManager(bonds=[
            make_bond("RU01", (BondEventType.OFFER, soon)),
            make_bond("RU02", (BondEventType.OFFER, far)),
        ])
        runner = make_runner(notifications, manager, monkeypatch)
        account = SimpleNamespace(id=uuid.uuid4())
        task = make_task(user, TaskType.BOND_EVENTS_MONITOR, {"brokers_account_id": str(account.id)})

        result = asyncio.run(runner._execute(
            task, FakeStrategyRepo(), FakeAccountRepo(account, owner_id=user.id)
        ))

        assert result == "notified about 1 bonds"
        text = notifications.sent[0][2]
        assert "RU01" in text
        assert "оферта" in text
        assert soon.strftime("%d.%m.%Y") in text
        # Далёкое событие пользователя пока не беспокоит.
        assert "RU02" not in text

    def test_reports_call_option(self, user, notifications, monkeypatch):
        soon = date.today() + timedelta(days=5)
        manager = FakeManager(bonds=[
            make_bond("RU03", (BondEventType.CALL_OPTION, soon), short_name="Облигация-3"),
        ])
        runner = make_runner(notifications, manager, monkeypatch)
        account = SimpleNamespace(id=uuid.uuid4())
        task = make_task(user, TaskType.BOND_EVENTS_MONITOR, {"brokers_account_id": str(account.id)})

        asyncio.run(runner._execute(
            task, FakeStrategyRepo(), FakeAccountRepo(account, owner_id=user.id)
        ))

        text = notifications.sent[0][2]
        assert "RU03 (Облигация-3)" in text
        assert "колл-опцион" in text

    def test_skips_far_events_only(self, user, notifications, monkeypatch):
        far = date.today() + timedelta(days=90)
        manager = FakeManager(bonds=[make_bond("RU04", (BondEventType.OFFER, far))])
        runner = make_runner(notifications, manager, monkeypatch)
        account = SimpleNamespace(id=uuid.uuid4())
        task = make_task(user, TaskType.BOND_EVENTS_MONITOR, {"brokers_account_id": str(account.id)})

        result = asyncio.run(runner._execute(
            task, FakeStrategyRepo(), FakeAccountRepo(account, owner_id=user.id)
        ))

        assert result == "no suitable bonds were found"
        assert notifications.sent == []

    def test_no_upcoming_offers(self, user, notifications, monkeypatch):
        manager = FakeManager(bonds=[])
        runner = make_runner(notifications, manager, monkeypatch)
        account = SimpleNamespace(id=uuid.uuid4())
        task = make_task(user, TaskType.BOND_EVENTS_MONITOR, {"brokers_account_id": str(account.id)})

        result = asyncio.run(runner._execute(
            task, FakeStrategyRepo(), FakeAccountRepo(account, owner_id=user.id)
        ))

        assert result == "no suitable bonds were found"
        assert notifications.sent == []

    def test_foreign_account_raises(self, user, notifications, monkeypatch):
        manager = FakeManager()
        runner = make_runner(notifications, manager, monkeypatch)
        task = make_task(user, TaskType.BOND_EVENTS_MONITOR, {"brokers_account_id": str(uuid.uuid4())})

        with pytest.raises(ValueError):
            asyncio.run(runner._execute(
                task, FakeStrategyRepo(), FakeAccountRepo(None, owner_id=None)
            ))
