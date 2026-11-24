"""Тесты репозитория общего справочника инструментов: upsert и ротации."""
import asyncio

from src.db.models.broker_instrument import BrokerInstrument
from src.db.repositories.broker_instruments_repository import BrokerInstrumentsRepository


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class FakeSession:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, stmt):
        return FakeResult(self.rows)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def make_row(uid, ticker, deleted_at=None):
    return BrokerInstrument(
        uid=uid,
        ticker=ticker,
        figi=None,
        isin=None,
        lot_size=1,
        type="share",
        sandbox=False,
        deleted_at=deleted_at,
    )


def test_inserts_new_and_soft_deletes_missing():
    existing = make_row("uid-old", "GAZP")
    session = FakeSession([existing])

    asyncio.run(BrokerInstrumentsRepository(session).replace_all(
        False, [("uid-new", "SBER", "figi", "isin", 10, "share")]
    ))

    assert [row.ticker for row in session.added] == ["SBER"]
    assert existing.deleted_at is not None
    assert session.commits == 1


def test_rotates_ticker_to_new_uid_in_place():
    existing = make_row("uid-old", "SBER")
    session = FakeSession([existing])

    asyncio.run(BrokerInstrumentsRepository(session).replace_all(
        False, [("uid-new", "SBER", None, None, 10, "share")]
    ))

    assert session.added == []
    assert existing.uid == "uid-new"
    assert existing.deleted_at is None


def test_revives_soft_deleted_row_with_same_ticker():
    existing = make_row("uid-old", "SBER", deleted_at=object())
    session = FakeSession([existing])

    asyncio.run(BrokerInstrumentsRepository(session).replace_all(
        False, [("uid-new", "SBER", None, None, 10, "share")]
    ))

    assert session.added == []
    assert existing.uid == "uid-new"
    assert existing.deleted_at is None


def test_rolls_back_on_error():
    class BrokenSession(FakeSession):
        async def execute(self, stmt):
            raise RuntimeError("db is down")

    session = BrokenSession()

    try:
        asyncio.run(BrokerInstrumentsRepository(session).replace_all(False, []))
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError")

    assert session.rollbacks == 1
