"""Тесты сборки индекса в PortfolioManager: состав из БД + цены/лоты у брокера."""
from datetime import date
from types import SimpleNamespace

import pytest

from src.core.portfolio_manager import PortfolioManager
from src.models.index_composition import CompositionRow, CompositionSnapshot
from src.models.positions import Cash, Positions, PositionsCash, PositionsInstrument


def make_snapshot():
    return CompositionSnapshot(
        index_name="IMOEX",
        tradedate=date(2026, 9, 25),
        rows=[
            CompositionRow(ticker="SBER", shortname="Сбербанк", weight=60.0),
            CompositionRow(ticker="GAZP", shortname="Газпром", weight=40.0),
        ],
    )


def make_share(ticker, uid=None, lot_size=10, isin=None):
    return SimpleNamespace(
        uid=uid or f"uid-{ticker}",
        ticker=ticker,
        lot_size=lot_size,
        isin=isin or f"isin-{ticker}",
    )


class FakeBroker:
    def __init__(self, shares, prices):
        self.shares = shares
        self.prices = prices
        self.price_calls = 0
        self.live_lookup_calls = 0

    def find_share(self, value, field="uid", directory=None):
        if directory is not None:
            meta = None
            if field == "ticker":
                meta = directory.by_ticker.get(value)
            elif field == "uid":
                meta = directory.by_uid.get(value)
            if meta is not None:
                return SimpleNamespace(
                    uid=meta.uid, ticker=meta.ticker,
                    lot_size=meta.lot_size, isin=meta.isin,
                )
            return None
        self.live_lookup_calls += 1
        return self.shares.get(value)

    def get_last_prices_by_uid(self, uids):
        self.price_calls += 1
        return {uid: self.prices[uid] for uid in uids if uid in self.prices}


def make_manager(shares, prices):
    manager = PortfolioManager(broker_token="token", sandbox=False)
    manager.broker = FakeBroker(shares, prices)
    return manager


class TestBuildIndex:

    def test_enriches_with_broker_data(self):
        manager = make_manager(
            {"SBER": make_share("SBER"), "GAZP": make_share("GAZP", lot_size=1)},
            {"uid-SBER": 300.0, "uid-GAZP": 150.0},
        )

        index = manager.get_index("IMOEX", make_snapshot())

        assert index.name == "IMOEX"
        assert index.date == "2026-09-25"
        by_ticker = {item.ticker: item for item in index.items}
        assert by_ticker["SBER"].last_price == 300.0
        assert by_ticker["SBER"].lot_size == 10
        assert by_ticker["SBER"].weight == 60.0
        assert by_ticker["GAZP"].lot_size == 1

    def test_missing_ticker_skipped_with_warning(self, caplog):
        manager = make_manager(
            {"SBER": make_share("SBER")},
            {"uid-SBER": 300.0},
        )

        with caplog.at_level("WARNING"):
            index = manager.get_index("IMOEX", make_snapshot())

        assert [item.ticker for item in index.items] == ["SBER"]
        assert "GAZP" in caplog.text

    def test_missing_price_skipped_with_warning(self, caplog):
        manager = make_manager(
            {"SBER": make_share("SBER"), "GAZP": make_share("GAZP")},
            {"uid-SBER": 300.0},
        )

        with caplog.at_level("WARNING"):
            index = manager.get_index("IMOEX", make_snapshot())

        assert [item.ticker for item in index.items] == ["SBER"]
        assert "GAZP" in caplog.text

    def test_all_missing_raises(self):
        manager = make_manager({}, {})

        with pytest.raises(ValueError):
            manager.get_index("IMOEX", make_snapshot())

    def test_cached_by_tradedate(self):
        manager = make_manager(
            {"SBER": make_share("SBER"), "GAZP": make_share("GAZP")},
            {"uid-SBER": 300.0, "uid-GAZP": 150.0},
        )
        snapshot = make_snapshot()

        manager.get_index("IMOEX", snapshot)
        manager.get_index("imoex", snapshot)

        assert manager.broker.price_calls == 1

    def test_uses_directory_without_live_lookups(self):
        from src.models.instrument_directory import InstrumentDirectory, InstrumentMeta

        manager = make_manager(
            {"SBER": make_share("SBER"), "GAZP": make_share("GAZP")},
            {"uid-SBER": 300.0, "uid-GAZP": 150.0},
        )
        directory = InstrumentDirectory(
            sandbox=False,
            updated_at=date(2026, 9, 25),
            by_ticker={
                "SBER": InstrumentMeta(
                    uid="uid-SBER", ticker="SBER", figi="figi", isin="isin-SBER",
                    lot_size=10, type="share",
                ),
                "GAZP": InstrumentMeta(
                    uid="uid-GAZP", ticker="GAZP", figi="figi", isin="isin-GAZP",
                    lot_size=1, type="share",
                ),
            },
            by_uid={},
        )

        index = manager.get_index("IMOEX", make_snapshot(), directory=directory)

        assert {item.ticker for item in index.items} == {"SBER", "GAZP"}
        assert manager.broker.live_lookup_calls == 0


def make_positions():
    return Positions(
        cash=PositionsCash(units=100000, nano=0, currency="rub"),
        shares=[
            PositionsInstrument(
                uid="uid-SBER",
                figi="figi",
                balance=10,
                last_price=Cash(units=300, nano=0),
                lot_size=10,
                ticker="SBER",
                type="share",
            )
        ],
    )


class FakeAccount:
    def __init__(self, positions):
        self.positions = positions

    def get_positions(self, directory=None):
        return self.positions


class TestCalculateRebalanceIndexDate:

    def test_preview_carries_index_date(self):
        from src.models.balancer_params import BalancerParams
        from decimal import Decimal

        manager = make_manager(
            {"SBER": make_share("SBER"), "GAZP": make_share("GAZP")},
            {"uid-SBER": 300.0, "uid-GAZP": 150.0},
        )
        manager.account_client = FakeAccount(make_positions())
        params = BalancerParams(
            delta=Decimal("0.05"),
            commission=Decimal("0.003"),
            min_lots_to_keep=1,
            max_cash=0,
        )

        preview = manager.calculate_rebalance("IMOEX", params, make_snapshot(), directory=None)

        assert preview.index_date == "2026-09-25"


class TestExecuteExplicitActions:

    def test_executes_given_list(self):
        from src.models.action import Action

        manager = make_manager({}, {})
        created = []

        class StubAccount:
            def create_order(self, action):
                created.append(action)
                return "ok"

        manager.account_client = StubAccount()
        share = make_share("SBER")
        actions = [Action(type="BUY", quantity=2, share=share)]

        success, errors = manager.execute_actions(actions)

        assert success == actions
        assert errors == []
        assert created == actions

    def test_none_executes_accumulated(self):
        manager = make_manager({}, {})
        manager.account_client = SimpleNamespace(
            create_order=lambda action: "ok"
        )

        success, errors = manager.execute_actions()

        assert success == []
        assert errors == []


def test_directory_contour_mismatch_raises():
    """Справочник чужого контура (песочница/бой) в расчёт не пускаем."""
    from src.models.instrument_directory import InstrumentDirectory

    manager = make_manager({}, {})
    directory = InstrumentDirectory(sandbox=True, updated_at=None)

    with pytest.raises(ValueError, match="contour"):
        manager.get_portfolio(directory=directory)
