"""Тесты сервиса синка составов индексов: парсинг analytics, замена слепка, ensure."""
import asyncio
import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.core.index_sync_service import IndexSyncService


def analytics_row(ticker, weight, shortname=None, tradedate="2026-09-25"):
    return ["IMOEX", tradedate, ticker, shortname or ticker, weight]


class FakeMoex:
    def __init__(self, data):
        self.data = data

    def load_index_rows(self, index_name):
        return self.data


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
    """Минимальная асинхронная сессия: execute/get/add/commit без БД."""

    def __init__(self, select_items=None, get_obj=None):
        self.select_items = select_items or []
        self.get_obj = get_obj
        self.added = []
        self.commits = 0

    async def execute(self, stmt):
        return FakeResult(self.select_items)

    async def get(self, model, pk):
        return self.get_obj

    def add(self, obj):
        self.added.append(obj)

    def add_all(self, objs):
        self.added.extend(objs)

    async def flush(self):
        return None

    async def rollback(self):
        return None

    async def commit(self):
        self.commits += 1


def make_index_row():
    return SimpleNamespace(
        id=uuid.uuid4(),
        index_name="IMOEX",
        composition_tradedate=None,
    )


class TestFetchRows:

    def test_parses_analytics(self):
        service = IndexSyncService(moex=FakeMoex([
            analytics_row("SBER", 14.77, "Сбербанк"),
            analytics_row("GAZP", 10.5, "Газпром"),
        ]))

        tradedate, rows = service.fetch_rows("imoex")

        assert tradedate == date(2026, 9, 25)
        assert rows == [
            ("SBER", "Сбербанк", Decimal("14.77")),
            ("GAZP", "Газпром", Decimal("10.5")),
        ]

    def test_empty_data_raises(self):
        service = IndexSyncService(moex=FakeMoex([]))

        with pytest.raises(ValueError):
            service.fetch_rows("IMOEX")

    def test_bad_tradedate_raises(self):
        service = IndexSyncService(moex=FakeMoex([
            analytics_row("SBER", 14.77, tradedate="not-a-date"),
        ]))

        with pytest.raises(ValueError):
            service.fetch_rows("IMOEX")

    def test_malformed_rows_skipped(self):
        service = IndexSyncService(moex=FakeMoex([
            analytics_row("SBER", 14.77),
            ["IMOEX", "2026-09-25", None, "Без тикера", 1.0],
            ["IMOEX", "2026-09-25", "BAD"],  # короткая строка
        ]))

        tradedate, rows = service.fetch_rows("IMOEX")

        assert [ticker for ticker, _, _ in rows] == ["SBER"]

    def test_all_rows_bad_raises(self):
        service = IndexSyncService(moex=FakeMoex([["IMOEX", "2026-09-25", "BAD"]]))

        with pytest.raises(ValueError):
            service.fetch_rows("IMOEX")


class TestSyncIndex:

    def test_replaces_snapshot(self):
        service = IndexSyncService(moex=FakeMoex([
            analytics_row("SBER", 14.77, "Сбербанк"),
        ]))
        index_row = make_index_row()
        session = FakeSession(get_obj=index_row)

        result = asyncio.run(
            service.sync_index(session, index_row.id, index_row.index_name)
        )

        assert result == "IMOEX: 1 tickers @ 2026-09-25"
        assert session.commits == 1
        tickers = [obj.ticker for obj in session.added]
        assert tickers == ["SBER"]

    def test_empty_moex_keeps_old_rows(self):
        """Пустой ответ биржи — ошибка до записи: старые строки не трогаем."""
        service = IndexSyncService(moex=FakeMoex([]))
        session = FakeSession()
        index_row = make_index_row()

        with pytest.raises(ValueError):
            asyncio.run(
                service.sync_index(session, index_row.id, index_row.index_name)
            )

        assert session.added == []
        assert session.commits == 0


def make_composition_row(ticker, weight="10.0", shortname=None):
    return SimpleNamespace(
        ticker=ticker, shortname=shortname, weight=Decimal(weight), tradedate=date(2026, 9, 25)
    )


class TestEnsureComposition:

    def test_returns_stored_snapshot(self):
        service = IndexSyncService(moex=FakeMoex([]))
        index_row = make_index_row()
        index_row.composition_tradedate = date(2026, 9, 25)
        session = FakeSession(select_items=[
            make_composition_row("SBER", "14.77", "Сбербанк"),
            make_composition_row("GAZP", "10.5", None),
        ])

        snapshot = asyncio.run(service.ensure_composition(session, index_row))

        assert snapshot.index_name == "IMOEX"
        assert snapshot.tradedate == date(2026, 9, 25)
        assert [(r.ticker, r.shortname, r.weight) for r in snapshot.rows] == [
            ("SBER", "Сбербанк", 14.77),
            ("GAZP", "GAZP", 10.5),  # shortname без названия — тикер
        ]

    def test_backfills_missing_composition(self):
        """Состава нет — разово тянем с биржи, повторного запроса состава не надо."""
        service = IndexSyncService(moex=FakeMoex([analytics_row("SBER", 14.77)]))
        index_row = make_index_row()

        calls = {"reads": 0}

        class BackfillSession(FakeSession):
            async def execute(self, stmt):
                # Первый SELECT (ensure) пуст, replace пишет, второй SELECT читает.
                if self.added:
                    return FakeResult([make_composition_row("SBER", "14.77")])
                calls["reads"] += 1
                return FakeResult([])

        snapshot = asyncio.run(
            service.ensure_composition(BackfillSession(get_obj=index_row), index_row)
        )

        assert [r.ticker for r in snapshot.rows] == ["SBER"]
        assert snapshot.tradedate == date(2026, 9, 25)

    def test_still_empty_raises(self):
        service = IndexSyncService(moex=FakeMoex([]))

        # Мок синка: биржа пуста, но ошибку глушим — строк всё равно нет.
        async def fake_sync_index(session, index_id, index_name):
            return "nothing"

        service.sync_index = fake_sync_index

        with pytest.raises(ValueError):
            asyncio.run(
                service.ensure_composition(FakeSession(), make_index_row())
            )


class TestSyncStrategyIndices:

    def test_one_failed_index_does_not_break_others(self, monkeypatch):
        from src.db.repositories.users_strategy_repository import UsersStrategyRepository

        service = IndexSyncService(moex=FakeMoex([]))
        session = FakeSession()
        indices = [(uuid.uuid4(), "BAD"), (uuid.uuid4(), "IMOEX")]

        async def fake_get(self):
            return indices

        monkeypatch.setattr(
            UsersStrategyRepository, "get_referenced_indices", fake_get
        )

        calls = []

        async def fake_sync(session, index_id, index_name):
            calls.append(index_name)
            if index_name == "BAD":
                raise RuntimeError("boom")
            return f"{index_name}: ok"

        monkeypatch.setattr(service, "sync_index", fake_sync)

        result = asyncio.run(service.sync_strategy_indices(session))

        assert calls == ["BAD", "IMOEX"]
        assert "synced: 1" in result
        assert "failed: 1" in result
