"""Отбор облигаций с предстоящими событиями (оферта, колл-опцион).

PortfolioManager собирает данные из двух источников: состав счёта у брокера и
справочник облигаций Мосбиржи. Оба подменяются фейками.
"""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from src.core.portfolio_manager import PortfolioManager
from src.models.bond import BondEventType, MoexBond, parse_moex_date

TODAY = date.today()
SOON = TODAY + timedelta(days=10)
LATER = TODAY + timedelta(days=200)
PAST = TODAY - timedelta(days=10)


def iso(value: date) -> str:
    return value.strftime("%Y-%m-%d")


def moex_bond(ticker, offer=None, call=None, put=None, short_name="Бумага"):
    return MoexBond(
        ticker=ticker,
        short_name=short_name,
        board_name="TQCB",
        lot_value=1000.0,
        offer_date=iso(offer) if offer else None,
        call_option_date=iso(call) if call else None,
        put_option_date=iso(put) if put else None,
        buy_back_price=100.0,
    )


def position(ticker, balance=5):
    return SimpleNamespace(
        uid=f"uid-{ticker}",
        figi=f"figi-{ticker}",
        ticker=ticker,
        lot_size=1,
        type="bond",
        balance=balance,
    )


@pytest.fixture
def manager(monkeypatch):
    """PortfolioManager с заглушёнными брокером и биржей."""
    monkeypatch.setattr(
        "src.core.portfolio_manager.TBroker", lambda **kwargs: SimpleNamespace()
    )
    monkeypatch.setattr("src.core.portfolio_manager.Moex", lambda: SimpleNamespace())

    instance = PortfolioManager(broker_token="token")
    instance.account_client = SimpleNamespace(account_id="acc-1")
    return instance


def setup_data(manager, positions, bonds):
    manager.account_client.get_positions = lambda: SimpleNamespace(bonds=positions, shares=[])
    manager.moex.get_bonds = lambda: bonds


class TestGetBondsWithEvents:

    def test_keeps_bond_with_upcoming_offer(self, manager):
        setup_data(manager, [position("RU01", balance=7)], [moex_bond("RU01", offer=SOON)])

        bonds = manager.get_bonds_with_events()

        assert len(bonds) == 1
        assert bonds[0].ticker == "RU01"
        assert bonds[0].balance == 7
        assert bonds[0].short_name == "Бумага"
        assert [(event.type, event.date) for event in bonds[0].events] == [
            (BondEventType.OFFER, SOON)
        ]

    def test_keeps_bond_with_call_option(self, manager):
        setup_data(manager, [position("RU02")], [moex_bond("RU02", call=SOON)])

        bonds = manager.get_bonds_with_events()

        assert [event.type for event in bonds[0].events] == [BondEventType.CALL_OPTION]

    def test_reports_both_events_sorted_by_date(self, manager):
        setup_data(manager, [position("RU03")], [moex_bond("RU03", offer=LATER, call=SOON)])

        events = manager.get_bonds_with_events()[0].events

        assert [event.date for event in events] == [SOON, LATER]
        assert [event.type for event in events] == [
            BondEventType.CALL_OPTION,
            BondEventType.OFFER,
        ]

    def test_skips_bond_without_events(self, manager):
        setup_data(manager, [position("RU04")], [moex_bond("RU04")])

        assert manager.get_bonds_with_events() == []

    def test_skips_past_events(self, manager):
        setup_data(manager, [position("RU05")], [moex_bond("RU05", offer=PAST)])

        assert manager.get_bonds_with_events() == []

    def test_ignores_put_option_only(self, manager):
        """Пут-опцион не относится к отслеживаемым событиям."""
        setup_data(manager, [position("RU06")], [moex_bond("RU06", put=SOON)])

        assert manager.get_bonds_with_events() == []

    def test_skips_bonds_not_in_portfolio(self, manager):
        setup_data(manager, [position("RU07")], [moex_bond("RU08", offer=SOON)])

        assert manager.get_bonds_with_events() == []

    def test_respects_since(self, manager):
        setup_data(manager, [position("RU09")], [moex_bond("RU09", offer=SOON)])

        assert manager.get_bonds_with_events(since=SOON) != []
        assert manager.get_bonds_with_events(since=SOON + timedelta(days=1)) == []


class TestParseMoexDate:

    @pytest.mark.parametrize("value", [None, "", "0000-00-00", "не дата", 0])
    def test_absent_or_broken(self, value):
        assert parse_moex_date(value) is None

    def test_iso_string(self):
        assert parse_moex_date("2026-08-01") == date(2026, 8, 1)

    def test_date_passthrough(self):
        assert parse_moex_date(date(2026, 8, 1)) == date(2026, 8, 1)
