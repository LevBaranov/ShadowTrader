"""Тесты параметров балансировщика: неснижаемый остаток и комиссия.

Все параметры приходят снаружи (BalancerParams) — настройки пользователя из БД,
у балансировщика своих значений по умолчанию нет.
"""
from decimal import Decimal

import pytest

from src.core.balancer import Balancer
from src.models.balancer_params import BalancerParams
from src.models.index import Index, IndexItem
from src.models.positions import Cash, Positions, PositionsCash, PositionsInstrument


def make_index(*items) -> Index:
    return Index(
        name="IMOEX",
        date="2026-08-04",
        items=[
            IndexItem(
                ticker=ticker,
                shortnames=ticker,
                weight=weight,
                lot_size=1,
                isin=f"RU{ticker}",
                last_price=price,
            )
            for ticker, weight, price in items
        ],
    )


def make_positions(cash: float) -> Positions:
    """Пустой портфель с деньгами: балансировщик будет только покупать."""
    return Positions(cash=PositionsCash(units=int(cash), nano=0, currency="rub"))


def buys(actions) -> dict[str, int]:
    return {a["ticker"]: a["quantity"] for a in actions if a["type"] == "BUY"}


def params(max_cash: int = 0, commission: str = "0.003") -> BalancerParams:
    """Параметры расчёта с прежними значениями из toml, кроме указанных."""
    return BalancerParams(
        delta=Decimal("0.05"),
        commission=Decimal(commission),
        min_lots_to_keep=1,
        max_cash=max_cash,
    )


@pytest.fixture
def index():
    # Два инструмента по 100 ₽ за лот, равные веса.
    return make_index(("AAA", 50.0, 100.0), ("BBB", 50.0, 100.0))


def test_spends_all_cash_without_reserve(index):
    balancer = Balancer(make_positions(1000), index, params())

    actions, free_cash = balancer.calculate_actions()

    assert sum(buys(actions).values()) > 0
    # Остаётся меньше цены лота с комиссией — тратим всё, что можем.
    assert free_cash < 100 * 1.003


def test_keeps_reserve(index):
    """С резервом 800 ₽ из 1000 покупок должно быть меньше, а остаток — не ниже резерва."""
    balancer = Balancer(make_positions(1000), index, params(max_cash=800))

    actions, free_cash = balancer.calculate_actions()

    assert sum(buys(actions).values()) == 1
    assert free_cash >= 800


def test_reserve_above_cash_blocks_purchases(index):
    balancer = Balancer(make_positions(1000), index, params(max_cash=1000))

    actions, free_cash = balancer.calculate_actions()

    assert buys(actions) == {}
    assert free_cash == pytest.approx(1000)


def test_reserve_reduces_purchase_count(index):
    without_reserve, _ = Balancer(
        make_positions(1000), index, params()
    ).calculate_actions()
    with_reserve, _ = Balancer(
        make_positions(1000), index, params(max_cash=500)
    ).calculate_actions()

    assert sum(buys(with_reserve).values()) < sum(buys(without_reserve).values())


class TestCommission:
    """Комиссия — настройка брокера, приходит в параметрах и влияет на расчёт."""

    def test_higher_commission_buys_less(self, index):
        """Комиссия удорожает лот, поэтому при высокой ставке купится меньше."""
        cheap, _ = Balancer(
            make_positions(1000), index, params(commission="0.0")
        ).calculate_actions()
        pricey, _ = Balancer(
            make_positions(1000), index, params(commission="0.5")
        ).calculate_actions()

        assert sum(buys(pricey).values()) < sum(buys(cheap).values())

    def test_prohibitive_commission_blocks_purchases(self, index):
        """Лот с комиссией дороже всего кэша — покупать нечего."""
        actions, free_cash = Balancer(
            make_positions(150), index, params(commission="0.9")
        ).calculate_actions()

        assert buys(actions) == {}
        assert free_cash == pytest.approx(150)

    def test_decimal_params_do_not_break_arithmetic(self, index):
        """Параметры приходят из БД как Decimal — расчёт не должен падать на float/Decimal."""
        actions, free_cash = Balancer(
            make_positions(1000), index, params(commission="0.003")
        ).calculate_actions()

        assert isinstance(free_cash, float)
        assert sum(buys(actions).values()) > 0


class TestSellExcludedInLots:
    """Исключённое из индекса продаётся лотами, а не штуками (кейс MSNG).

    PostOrderRequest.quantity — лоты. Отправка balance в штуках превышает
    позицию в lot_size раз: брокер видит шорт и отклоняет заявку
    («Account margin status is disabled» при выключенной марже).
    """

    def msng_positions(self, balance: int) -> Positions:
        """1000 шт. MSNG = 1 лот по ~1.34 ₽, денег нет — только продажа."""
        return Positions(
            cash=PositionsCash(units=0, nano=0, currency="rub"),
            shares=[
                PositionsInstrument(
                    uid="uid-msng",
                    figi="BBG000000000",
                    balance=balance,
                    last_price=Cash(units=1, nano=340_000_000),
                    lot_size=1000,
                    ticker="MSNG",
                    type="share",
                )
            ],
        )

    @staticmethod
    def sells(actions) -> dict[str, int]:
        return {a["ticker"]: a["quantity"] for a in actions if a["type"] == "SELL"}

    def test_excluded_sells_whole_lots(self, index):
        actions, _ = Balancer(
            self.msng_positions(1000), index, params()
        ).calculate_actions()

        assert self.sells(actions) == {"MSNG": 1}

    def test_excluded_sells_floor_lots(self, index):
        actions, _ = Balancer(
            self.msng_positions(2500), index, params()
        ).calculate_actions()

        assert self.sells(actions) == {"MSNG": 2}

    def test_excluded_less_than_lot_sells_nothing(self, index):
        actions, _ = Balancer(
            self.msng_positions(500), index, params()
        ).calculate_actions()

        assert self.sells(actions) == {}
