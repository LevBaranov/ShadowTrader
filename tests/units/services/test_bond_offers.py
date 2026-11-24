"""Оферты из bondization: парсинг API, раздача задач и уведомления планировщика."""
import asyncio
import uuid
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from src.core.crypto import encrypt_token
from src.db.enums import TaskType
from src.models.bond import BondEventType, MoexBond
from src.models.scheduler_frequency import ScheduleFrequency
from src.scheduler.runner import SchedulerRunner, ensure_bonds_offer_date_sync_task
from src.services.stock_market import Moex

TODAY = date.today()
ACC_ID = str(uuid.uuid4())
SOON = TODAY + timedelta(days=5)


def offers_page(columns, rows):
    return {"offers": {"columns": columns, "data": rows}}


def offer_row(secid, isin, start):
    return [isin, "Оферта", 1000, None, start, None, None, secid, "Оферта", "TQCB"]


OFFER_COLUMNS = [
    "isin", "name", "issuevalue", "offerdate", "offerdatestart",
    "offerdateend", "facevalue", "secid", "offertype", "primary_boardid",
]


class TestGetBondOffers:

    def test_parses_single_page(self, mocker):
        page = offers_page(OFFER_COLUMNS, [
            offer_row("RU01", "ISIN01", SOON.isoformat()),
            # Окно подачи не задано — бумагу пропускаем.
            offer_row("RU02", "ISIN02", None),
        ])
        mock_response = mocker.Mock()
        mock_response.json.return_value = page
        mock_session = mocker.Mock()
        mock_session.get.return_value = mock_response

        moex = Moex()
        moex.session = mock_session

        offers = moex.get_bond_offers(TODAY)

        assert offers == [("RU01", "ISIN01", SOON)]
        # from передаётся в ISO-формате вместе с лимитом и стартом пагинации.
        params = mock_session.get.call_args.kwargs["params"]
        assert params["from"] == TODAY.isoformat()
        assert params["offers.limit"] == 100

    def test_paginates_until_short_page(self, mocker):
        full = offers_page(OFFER_COLUMNS, [
            offer_row(f"RU{i:02d}", f"ISIN{i:02d}", SOON.isoformat()) for i in range(100)
        ])
        tail = offers_page(OFFER_COLUMNS, [offer_row("RUTAIL", "ISINTAIL", SOON.isoformat())])
        responses = []
        for page in (full, tail):
            response = mocker.Mock()
            response.json.return_value = page
            responses.append(response)
        mock_session = mocker.Mock()
        mock_session.get.side_effect = responses

        moex = Moex()
        moex.session = mock_session

        offers = moex.get_bond_offers(TODAY)

        assert len(offers) == 101
        assert offers[-1][0] == "RUTAIL"
        starts = [
            call.kwargs["params"]["offers.start"] for call in mock_session.get.call_args_list
        ]
        assert starts == [0, 100]

    def test_missing_column_raises_error(self, mocker):
        page = offers_page(["isin", "secid"], [offer_row("RU01", "ISIN01", SOON.isoformat())])
        mock_response = mocker.Mock()
        mock_response.json.return_value = page
        mock_session = mocker.Mock()
        mock_session.get.return_value = mock_response

        moex = Moex()
        moex.session = mock_session

        from src.models.error import Error
        with pytest.raises(Error):
            moex.get_bond_offers(TODAY)


def make_moex_bond(ticker, offer_start=None):
    return MoexBond(
        ticker=ticker,
        short_name="Бумага",
        board_name="TQCB",
        lot_value=1000.0,
        offer_date=None,
        call_option_date=None,
        put_option_date=None,
        buy_back_price=100.0,
        offer_start_date=offer_start,
    )


class TestMoexBondEvents:

    def test_offer_start_is_an_event(self):
        bond = make_moex_bond("RU01", offer_start=SOON)
        events = bond.events()
        assert (BondEventType.OFFER_START, SOON) in [(e.type, e.date) for e in events]

    def test_no_offer_start_no_event(self):
        bond = make_moex_bond("RU02")
        assert all(event.type != BondEventType.OFFER_START for event in bond.events())


class FakeNotifications:
    def __init__(self):
        self.sent = []

    async def notify(self, user, subject, text):
        self.sent.append((user, subject, text))


class FakeAccountRepo:
    def __init__(self, account=None, owner_id=None):
        self.account = account
        self.owner_id = owner_id

    async def get_for_user(self, account_pk, user_id):
        if self.account is not None and user_id == self.owner_id:
            return self.account
        return None


class FakeInstrumentService:
    async def ensure_directory(self, session, token, sandbox, must_contain=frozenset()):
        from src.models.instrument_directory import InstrumentDirectory
        return InstrumentDirectory(sandbox=sandbox, updated_at=None)


class FakeManager:
    def __init__(self, bonds=None):
        self.bonds = bonds or []

    def get_bonds_with_events(self, account_id=None, since=None, directory=None, moex_bonds=None):
        return self.bonds


class FakeTaskRepo:
    def __init__(self):
        self.created = []
        self.disabled = []

    async def get_active_tasks_by_type(self, task_type):
        return [task for task in getattr(self, "tasks", []) if task.task_type == task_type]

    async def get_user_tasks(self, user_id, **params_filters):
        return [task for task in getattr(self, "tasks", []) if task.user_id == user_id]

    async def create_task(self, task_type, frequency, user, params, last_checked_date):
        self.created.append((task_type, frequency, user, params, last_checked_date))
        return SimpleNamespace(id=uuid.uuid4())

    async def disable_task(self, task_id):
        self.disabled.append(task_id)
        return SimpleNamespace(id=task_id)


class FakeMoex:
    def __init__(self, offers=None):
        self.offers = offers or []

    def get_bond_offers(self, from_date):
        self.fetched_from = from_date
        return self.offers


class FakeBondCache:
    def __init__(self, moex=None):
        self.moex = moex or FakeMoex()
        self.calls = []

    async def get_bonds(self, session):
        self.calls.append(session)
        return []


class FakeBondsRepo:
    def __init__(self, stored=None, new_offers=None):
        self.stored = stored or []          # хранимые даты: [(secid, isin, date)]
        self.new_offers = new_offers
        self.updated = None

    async def known_offer_start_dates(self, offers):
        if self.new_offers is not None:
            return self.new_offers
        stored = {secid: d for secid, _isin, d in self.stored}
        return [o for o in offers if stored.get(o[0]) != o[2]]

    async def update_offer_start_dates(self, offers):
        self.updated = offers


def make_task(user, task_type, params):
    return SimpleNamespace(
        id=uuid.uuid4(),
        task_type=task_type,
        frequency=ScheduleFrequency.DAILY,
        user_id=user.id if user else None,
        user=user,
        params=params,
        last_checked_date=datetime.now() - timedelta(days=10),
        disabled_date=None,
    )


def make_runner(notifications, manager, monkeypatch, task_repo, bonds_repo, moex=None):
    runner = SchedulerRunner(
        session_factory=None,
        notifications=notifications,
        portfolio_manager_factory=None,
        instrument_service=FakeInstrumentService(),
    )
    monkeypatch.setattr(
        "src.scheduler.runner.build_portfolio_manager_for_account",
        lambda account, factory: manager,
    )
    monkeypatch.setattr("src.scheduler.runner.TaskRepository", lambda session: task_repo)
    monkeypatch.setattr(
        "src.scheduler.runner.MoexBondsRepository", lambda session: bonds_repo
    )
    if moex is not None:
        monkeypatch.setattr(
            "src.scheduler.runner.MoexBondCacheService",
            lambda: FakeBondCache(moex),
        )
    return runner


class TestOffersDateSync:

    @pytest.fixture
    def cache(self, monkeypatch):
        def make_cache(moex=None):
            cache = FakeBondCache(moex)
            monkeypatch.setattr("src.scheduler.runner.MoexBondCacheService", lambda: cache)
            return cache
        return make_cache

    def test_creates_task_for_monitor_owners(self, cache, monkeypatch):
        task_repo = FakeTaskRepo()
        user = SimpleNamespace(id=uuid.uuid4())
        task_repo.tasks = [make_task(
            user, TaskType.BOND_EVENTS_MONITOR, {"brokers_account_id": ACC_ID}
        )]
        bonds_repo = FakeBondsRepo(new_offers=[("RU01", "ISIN01", SOON)])
        moex = FakeMoex(offers=[("RU01", "ISIN01", SOON)])
        runner = make_runner(
            FakeNotifications(), FakeManager(), monkeypatch, task_repo, bonds_repo, moex
        )

        result = asyncio.run(runner._run_offers_date_sync(session="session"))

        assert len(task_repo.created) == 1
        task_type, frequency, created_user, params, last_checked = task_repo.created[0]
        assert task_type == TaskType.NOTIFY_START_OFFER_DATE
        assert frequency == ScheduleFrequency.DAILY
        assert created_user is user
        assert params == {"brokers_account_id": ACC_ID}
        assert last_checked < datetime(2000, 1, 2)
        # Даты сохранены — на следующем проходе они уже не «новые».
        assert bonds_repo.updated == [("RU01", "ISIN01", SOON)]
        assert result == "created 1 tasks for 1 bonds"
        # bondization запрошен с небольшим отступом назад.
        assert moex.fetched_from <= date.today() - timedelta(days=1)

    def test_unchanged_dates_create_nothing(self, cache, monkeypatch):
        task_repo = FakeTaskRepo()
        bonds_repo = FakeBondsRepo(stored=[("RU01", "ISIN01", SOON)])
        moex = FakeMoex(offers=[("RU01", "ISIN01", SOON)])
        runner = make_runner(
            FakeNotifications(), FakeManager(), monkeypatch, task_repo, bonds_repo, moex
        )

        result = asyncio.run(runner._run_offers_date_sync(session="session"))

        assert task_repo.created == []
        assert result == "no new offer start dates"

    def test_skips_when_pending_notification_task_exists(self, cache, monkeypatch):
        task_repo = FakeTaskRepo()
        user = SimpleNamespace(id=uuid.uuid4())
        task_repo.tasks = [
            make_task(user, TaskType.BOND_EVENTS_MONITOR, {"brokers_account_id": ACC_ID}),
            make_task(user, TaskType.NOTIFY_START_OFFER_DATE, {"brokers_account_id": ACC_ID}),
        ]
        bonds_repo = FakeBondsRepo(new_offers=[("RU02", "ISIN02", SOON)])
        moex = FakeMoex(offers=[("RU02", "ISIN02", SOON)])
        runner = make_runner(
            FakeNotifications(), FakeManager(), monkeypatch, task_repo, bonds_repo, moex
        )

        result = asyncio.run(runner._run_offers_date_sync(session="session"))

        assert task_repo.created == []
        assert bonds_repo.updated == [("RU02", "ISIN02", SOON)]
        assert result == "created 0 tasks for 1 bonds"


class TestOffersNotification:

    @pytest.fixture
    def cache(self, monkeypatch):
        cache = FakeBondCache()
        monkeypatch.setattr("src.scheduler.runner.MoexBondCacheService", lambda: cache)
        return cache

    def test_notifies_and_disables_task(self, cache, monkeypatch):
        task_repo = FakeTaskRepo()
        user = SimpleNamespace(id=uuid.uuid4())
        notifications = FakeNotifications()
        manager = FakeManager(bonds=[
            SimpleNamespace(ticker="RU01", short_name="Бумага-1", events=[
                SimpleNamespace(type=BondEventType.OFFER_START, date=SOON),
            ]),
            SimpleNamespace(ticker="RU09", short_name="Бумага-9", events=[
                SimpleNamespace(type=BondEventType.OFFER, date=SOON),
            ]),
        ])
        runner = make_runner(notifications, manager, monkeypatch, task_repo, FakeBondsRepo())
        task = make_task(user, TaskType.NOTIFY_START_OFFER_DATE, {"brokers_account_id": ACC_ID})

        result = asyncio.run(runner._execute(
            task, None, FakeAccountRepo(SimpleNamespace(id=ACC_ID, users_broker=SimpleNamespace(broker_token=encrypt_token("t.token"), sandbox=False)), owner_id=user.id),
            session="session",
        ))

        assert result == "notified about 1 bonds"
        assert len(notifications.sent) == 1
        _user, subject, text = notifications.sent[0]
        assert "оферту" in subject
        assert "RU01" in text
        assert "начало подачи заявок" in text
        # Разовая задача: следующий цикл планировщика её пропускает.
        assert task_repo.disabled == [task.id]

    def test_no_matching_positions_still_disables(self, cache, monkeypatch):
        task_repo = FakeTaskRepo()
        user = SimpleNamespace(id=uuid.uuid4())
        notifications = FakeNotifications()
        runner = make_runner(
            notifications, FakeManager(bonds=[]), monkeypatch, task_repo, FakeBondsRepo()
        )
        task = make_task(user, TaskType.NOTIFY_START_OFFER_DATE, {"brokers_account_id": ACC_ID})

        result = asyncio.run(runner._execute(
            task, None, FakeAccountRepo(SimpleNamespace(id=ACC_ID, users_broker=SimpleNamespace(broker_token=encrypt_token("t.token"), sandbox=False)), owner_id=user.id),
            session="session",
        ))

        assert result == "no suitable bonds were found"
        assert notifications.sent == []
        assert task_repo.disabled == [task.id]

    def test_foreign_account_disables_and_raises(self, cache, monkeypatch):
        task_repo = FakeTaskRepo()
        user = SimpleNamespace(id=uuid.uuid4())
        runner = make_runner(
            FakeNotifications(), FakeManager(), monkeypatch, task_repo, FakeBondsRepo()
        )
        task = make_task(user, TaskType.NOTIFY_START_OFFER_DATE, {"brokers_account_id": ACC_ID})

        with pytest.raises(ValueError):
            asyncio.run(runner._execute(
                task, None, FakeAccountRepo(None, owner_id=None), session="session",
            ))

        assert task_repo.disabled == [task.id]


class TestEnsureBondsOfferDateSyncTask:

    def _run(self, monkeypatch, repo):
        import src.scheduler.runner as runner_module
        monkeypatch.setattr(runner_module, "TaskRepository", lambda session: repo)

        def session_factory():
            class Session:
                async def __aenter__(self):
                    return "session"

                async def __aexit__(self, *args):
                    return False
            return Session()

        asyncio.run(ensure_bonds_offer_date_sync_task(session_factory))

    def test_creates_when_missing(self, monkeypatch):
        class Repo:
            created = None

            async def get_active_system_task(self, task_type):
                return None

            async def create_task(self, task_type, frequency, user, params, last_checked_date):
                Repo.created = (task_type, frequency, user, params, last_checked_date)

        repo = Repo()
        self._run(monkeypatch, repo)

        assert repo.created is not None
        task_type, frequency, user, params, _ = repo.created
        assert task_type == TaskType.MOEX_BONDS_OFFER_DATE_SYNC
        assert frequency == ScheduleFrequency.DAILY
        assert user is None

    def test_skips_when_exists(self, monkeypatch):
        class Repo:
            async def get_active_system_task(self, task_type):
                return SimpleNamespace(id=uuid.uuid4())

            async def create_task(self, *args):
                raise AssertionError("should not create")
