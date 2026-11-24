"""Тесты справочника облигаций MOEX: upsert и даты подачи заявок."""
import asyncio
from datetime import date

from src.db.models.moex_bond import MoexBond as DBMoexBond
from src.db.repositories.moex_bond_repository import MoexBondsRepository
from src.models.bond import MoexBond


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
        self.deleted = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, stmt):
        return FakeResult(self.rows)

    async def scalar(self, stmt):
        return self.rows[0] if self.rows else None

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def make_bond(secid, isin=None):
    return MoexBond(
        ticker=secid,
        short_name=secid,
        board_name="TQCB",
        lot_value=1.0,
        offer_date=None,
        call_option_date=None,
        put_option_date=None,
        buy_back_price=0.0,
        isin=isin,
    )


def test_replace_all_updates_existing_and_deletes_stale():
    existing = DBMoexBond(secid="SBER", isin="ISIN1", offer_start_date=date(2026, 1, 1))
    stale = DBMoexBond(secid="OLD")
    session = FakeSession([existing, stale])

    asyncio.run(MoexBondsRepository(session).replace_all([make_bond("SBER", "ISIN1")]))

    assert existing.short_name == "SBER"
    assert existing.offer_start_date == date(2026, 1, 1)
    assert session.deleted == [stale]
    assert session.commits == 1


def test_replace_all_adds_new_rows():
    session = FakeSession()

    asyncio.run(MoexBondsRepository(session).replace_all([make_bond("SBER")]))

    assert [row.secid for row in session.added] == ["SBER"]
    assert session.commits == 1


def test_known_offer_start_dates_returns_only_changed():
    row = DBMoexBond(secid="SBER", isin="ISIN1", offer_start_date=date(2026, 1, 1))
    session = FakeSession([row])
    offers = [
        ("SBER", "ISIN1", date(2026, 1, 1)),
        ("SBER", "ISIN1", date(2026, 2, 1)),
    ]

    result = asyncio.run(MoexBondsRepository(session).known_offer_start_dates(offers))

    assert result == [("SBER", "ISIN1", date(2026, 2, 1))]


def test_update_offer_start_dates_by_isin():
    row = DBMoexBond(secid="OTHER", isin="ISIN1")
    session = FakeSession([row])

    updated = asyncio.run(
        MoexBondsRepository(session).update_offer_start_dates(
            [("SBER", "ISIN1", date(2026, 3, 1))]
        )
    )

    assert updated == 1
    assert row.offer_start_date == date(2026, 3, 1)
