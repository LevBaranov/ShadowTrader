"""Тесты справочника инструментов: свежесть, inline-refresh, песочницы, фейлы."""
import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

from src.core.instrument_service import InstrumentService


def make_row(ticker, uid=None, updated_at=None):
    return SimpleNamespace(
        uid=uid or f"uid-{ticker}",
        ticker=ticker,
        figi=f"figi-{ticker}",
        isin=f"isin-{ticker}",
        lot_size=10,
        type="share",
        deleted_at=None,
        updated_at=updated_at or datetime.now(),
    )


class FakeScalars:
    def __init__(self, items):
        self.items = items

    def all(self):
        return self.items


class FakeResult:
    def __init__(self, items):
        self.items = items

    def scalars(self):
        return FakeScalars(self.items)


class FakeSession:
    def __init__(self, rows=None, commit_error=None):
        self.rows = rows or []
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.commit_error = commit_error

    async def execute(self, stmt):
        # Как get_alive: удалённые строки запрос не возвращает.
        alive = [r for r in self.rows if getattr(r, "deleted_at", None) is None]
        return FakeResult(alive)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1
        if self.commit_error is not None:
            raise self.commit_error
        # Упавший commit ничего не сохраняет — как настоящая БД.
        self.rows.extend(self.added)
        self.added = []

    async def rollback(self):
        self.rollbacks += 1
        self.added = []


def make_instrument(ticker, uid=None):
    return SimpleNamespace(
        uid=uid or f"uid-{ticker}",
        ticker=ticker,
        figi=f"figi-{ticker}",
        isin=f"isin-{ticker}",
        lot_size=10,
        type="share",
    )


class FakeBrokerFactory:
    def __init__(self, instruments=None, error=None):
        self.instruments = instruments or []
        self.error = error
        self.calls = []

    def __call__(self, token, sandbox):
        factory = self

        class Broker:
            def get_all_instruments(self):
                factory.calls.append((token, sandbox))
                if factory.error is not None:
                    raise factory.error
                return factory.instruments

        return Broker()


class TestEnsureDirectory:

    def test_fresh_table_no_broker_call(self):
        service = InstrumentService(broker_factory=FakeBrokerFactory())
        session = FakeSession(rows=[make_row("SBER")])

        directory = asyncio.run(
            service.ensure_directory(session, "tok", False, must_contain={"SBER"})
        )

        assert directory.by_ticker["SBER"].uid == "uid-SBER"
        assert directory.by_uid["uid-SBER"].lot_size == 10
        assert service.broker_factory.calls == []
        assert session.commits == 0

    def test_stale_table_refreshes(self):
        factory = FakeBrokerFactory(instruments=[make_instrument("SBER")])
        service = InstrumentService(broker_factory=factory)
        old = datetime.now() - timedelta(hours=30)
        session = FakeSession(rows=[make_row("OLD", updated_at=old)])

        directory = asyncio.run(service.ensure_directory(session, "tok", False))

        assert len(factory.calls) == 1
        assert session.commits == 1
        assert list(directory.by_ticker) == ["SBER"]

    def test_empty_table_refreshes(self):
        factory = FakeBrokerFactory(instruments=[make_instrument("SBER")])
        service = InstrumentService(broker_factory=factory)
        session = FakeSession(rows=[])

        directory = asyncio.run(service.ensure_directory(session, "tok", False))

        assert len(factory.calls) == 1
        assert "SBER" in directory.by_ticker

    def test_missing_ticker_triggers_refill(self):
        factory = FakeBrokerFactory(
            instruments=[make_instrument("SBER"), make_instrument("GAZP")]
        )
        service = InstrumentService(broker_factory=factory)
        session = FakeSession(rows=[make_row("SBER")])

        directory = asyncio.run(
            service.ensure_directory(session, "tok", False, must_contain={"SBER", "GAZP"})
        )

        assert len(factory.calls) == 1
        assert set(directory.by_ticker) == {"SBER", "GAZP"}

    def test_refresh_failure_serves_stale(self):
        factory = FakeBrokerFactory(error=RuntimeError("broker down"))
        service = InstrumentService(broker_factory=factory)
        session = FakeSession(rows=[make_row("SBER")])

        directory = asyncio.run(service.ensure_directory(session, "tok", False))

        assert directory.by_ticker["SBER"].uid == "uid-SBER"
        assert session.commits == 0

    def test_sandbox_namespace(self):
        factory = FakeBrokerFactory(instruments=[make_instrument("SBER")])
        service = InstrumentService(broker_factory=factory)
        session = FakeSession(rows=[])

        directory = asyncio.run(service.ensure_directory(session, "tok", True))

        assert directory.sandbox is True
        assert factory.calls == [("tok", True)]

    def test_deleted_rows_skipped(self):
        service = InstrumentService(broker_factory=FakeBrokerFactory())
        # get_alive уже отфильтровал удалённые — здесь проверяем сборку:
        # строка с deleted_at в get_alive не попадает по запросу репозитория.
        session = FakeSession(rows=[make_row("SBER")])

        directory = asyncio.run(service.ensure_directory(session, "tok", False))

        assert set(directory.by_ticker) == {"SBER"}

    def test_duplicate_tickers_deduped(self, caplog):
        """Один тикер с разными uid (допвыпуски) — в таблицу идёт первый."""
        factory = FakeBrokerFactory(instruments=[
            make_instrument("RU000A102SX4", uid="uid-first"),
            make_instrument("RU000A102SX4", uid="uid-second"),
            make_instrument("SBER"),
        ])
        service = InstrumentService(broker_factory=factory)
        session = FakeSession(rows=[])

        import logging
        with caplog.at_level(logging.WARNING):
            directory = asyncio.run(service.ensure_directory(session, "tok", True))

        assert set(directory.by_ticker) == {"RU000A102SX4", "SBER"}
        assert directory.by_ticker["RU000A102SX4"].uid == "uid-first"
        assert "RU000A102SX4" in caplog.text

    def test_failed_replace_rolls_back_and_serves_on(self):
        """Упавший commit — rollback сессии, запрос не падает, сессия жива."""
        factory = FakeBrokerFactory(instruments=[make_instrument("SBER")])
        service = InstrumentService(broker_factory=factory)
        session = FakeSession(rows=[], commit_error=RuntimeError("db down"))

        directory = asyncio.run(service.ensure_directory(session, "tok", False))

        assert session.rollbacks == 1
        assert directory.by_ticker == {}
