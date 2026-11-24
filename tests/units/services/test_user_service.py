"""Тесты UserService: стратегия по счёту, пропавшему у брокера, показывается неактивной."""
import asyncio
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.core.crypto import encrypt_token
from src.core.user_service import AccountDeletedError, UserService
from src.models.index_composition import CompositionSnapshot
from src.services.broker import BrokerAccountNotFoundError


class FakeStrategyRepo:
    session = None

    def __init__(self, strategies):
        self.strategies = strategies

    async def get_user_strategies(self, user_id):
        return self.strategies

    async def get_user_strategy(self, user_id, strategy_id):
        for strategy in self.strategies:
            if strategy.id == strategy_id:
                return strategy
        return None


class NotFoundManager:
    """Портфельный менеджер счёта, которого больше нет у брокера."""

    broker = None

    def calculate_rebalance(self, index_name, params, composition=None, directory=None):
        raise BrokerAccountNotFoundError("Account not found in broker")


class FakeIndexSync:
    async def ensure_composition(self, session, index_row):
        return CompositionSnapshot(index_name="IMOEX", tradedate=None, rows=[])


class FakeInstrumentService:
    async def ensure_directory(self, session, token, sandbox, must_contain=frozenset(), broker=None):
        from src.models.instrument_directory import InstrumentDirectory
        return InstrumentDirectory(sandbox=sandbox, updated_at=None)


def make_strategy(deleted_at=None):
    users_broker = SimpleNamespace(
        id=uuid.uuid4(),
        broker_name="T-Bank",
        broker_token=encrypt_token("t.token"),
        commission=Decimal("0.003"),
        sandbox=False,
    )
    return SimpleNamespace(
        id=uuid.uuid4(),
        brokers_account=SimpleNamespace(
            id=uuid.uuid4(),
            account_id="acc-1",
            account_name="Брокерский счёт",
            deleted_at=deleted_at,
            users_broker=users_broker,
        ),
        stock_markets_index=SimpleNamespace(id=uuid.uuid4(), index_name="IMOEX"),
        max_cash=0,
        delta=Decimal("0.05"),
        min_lots_to_keep=1,
    )


@pytest.fixture
def user():
    return SimpleNamespace(id=uuid.uuid4())


def make_service(monkeypatch, strategies):
    service = UserService(
        strategy_repo=FakeStrategyRepo(strategies),
        portfolio_manager_factory=None,
        index_sync=FakeIndexSync(),
        instrument_service=FakeInstrumentService(),
    )
    monkeypatch.setattr(
        "src.core.user_service.build_portfolio_manager_for_account",
        lambda account, factory: NotFoundManager(),
    )
    return service


def test_strategy_shown_inactive_when_account_missing_in_broker(user, monkeypatch):
    """Счёт ещё не помечен deleted_at, но брокер отвечает NOT_FOUND — не 500,
    а карточка стратегии с account_deleted=True и пустым портфелем."""
    strategy = make_strategy()
    service = make_service(monkeypatch, [strategy])

    result = asyncio.run(service.get_user_strategies(user))

    assert len(result) == 1
    assert result[0].account_deleted is True
    assert result[0].portfolio == []
    assert result[0].free_cash == 0.0
    assert result[0].free_cash_after == 0.0


def test_rebalance_preview_missing_account_raises_account_deleted(user, monkeypatch):
    strategy = make_strategy()
    service = make_service(monkeypatch, [strategy])

    with pytest.raises(AccountDeletedError):
        asyncio.run(service.calculate_strategy_rebalance(user, strategy.id))


def test_rebalance_execute_missing_account_raises_account_deleted(user, monkeypatch):
    strategy = make_strategy(deleted_at=object())
    service = make_service(monkeypatch, [strategy])

    with pytest.raises(AccountDeletedError):
        asyncio.run(service.execute_strategy_rebalance(user, strategy.id, actions=[]))


class PlannedManager:
    """Менеджер для готового плана: пересчёт запрещён, исполнение пишем."""

    def __init__(self, broker):
        self.broker = broker
        self.executed_with = None

    def calculate_rebalance(self, *args, **kwargs):
        raise AssertionError("planned execution must not recalculate")

    def execute_actions(self, actions=None):
        self.executed_with = actions
        return list(actions or []), []


class PlannedBroker:
    def __init__(self, shares):
        self.shares = shares

    def find_share(self, value, field="uid", directory=None):
        return self.shares.get(value)


def make_planned_service(monkeypatch, strategy, shares):
    manager = PlannedManager(PlannedBroker(shares))
    monkeypatch.setattr(
        "src.core.user_service.build_portfolio_manager_for_account",
        lambda account, factory: manager,
    )
    service = UserService(
        strategy_repo=FakeStrategyRepo([strategy]),
        portfolio_manager_factory=None,
        index_sync=FakeIndexSync(),
        instrument_service=FakeInstrumentService(),
    )
    return service, manager


def make_share_obj(ticker):
    return SimpleNamespace(uid=f"uid-{ticker}", ticker=ticker)


def test_execute_planned_runs_without_recalculation(user, monkeypatch):
    from src.models.rebalance import PlannedAction

    strategy = make_strategy()
    service, manager = make_planned_service(
        monkeypatch, strategy, {"SBER": make_share_obj("SBER")}
    )

    result = asyncio.run(service.execute_strategy_rebalance(
        user, strategy.id,
        actions=[PlannedAction(type="BUY", ticker="SBER", quantity=2)],
    ))

    assert [a.share.ticker for a in manager.executed_with] == ["SBER"]
    assert len(result.success) == 1
    assert result.success[0].ticker == "SBER"
    assert result.success[0].quantity == 2
    assert result.errors == []


def test_execute_planned_unknown_ticker_goes_to_errors(user, monkeypatch):
    from src.models.rebalance import PlannedAction

    strategy = make_strategy()
    service, manager = make_planned_service(
        monkeypatch, strategy, {"SBER": make_share_obj("SBER")}
    )

    result = asyncio.run(service.execute_strategy_rebalance(
        user, strategy.id,
        actions=[
            PlannedAction(type="BUY", ticker="SBER", quantity=1),
            PlannedAction(type="SELL", ticker="NOPE", quantity=3),
        ],
    ))

    assert [a.share.ticker for a in manager.executed_with] == ["SBER"]
    assert len(result.success) == 1
    assert len(result.errors) == 1
    assert result.errors[0].ticker == "NOPE"
    assert result.errors[0].quantity == 3
    assert "NOPE" in (result.errors[0].description or "")


def test_execute_empty_actions_is_noop(user, monkeypatch):
    """Пустой список — no-op: не пересчитываем и не исполняем."""
    strategy = make_strategy()
    service, manager = make_planned_service(
        monkeypatch, strategy, {"SBER": make_share_obj("SBER")}
    )

    result = asyncio.run(service.execute_strategy_rebalance(
        user, strategy.id, actions=[],
    ))

    assert manager.executed_with == []
    assert result.success == [] and result.errors == []


def test_deleted_account_shown_with_empty_portfolio(user, monkeypatch):
    """Счёт с deleted_at не роняет список: пустой портфель, account_deleted=True."""
    strategy = make_strategy(deleted_at=object())
    service = make_service(monkeypatch, [strategy])

    result = asyncio.run(service.get_user_strategies(user))

    assert len(result) == 1
    assert result[0].account_deleted is True
    assert result[0].portfolio == []


def test_one_broken_strategy_does_not_break_list(user, monkeypatch):
    """Одна стратегия без данных — пустая карточка, остальные остаются."""
    strategy = make_strategy()
    service = make_service(monkeypatch, [strategy])

    async def boom(*args, **kwargs):
        raise ValueError("Нет данных для расчёта")

    monkeypatch.setattr(service, "_load_strategy_preview_by_snapshot", boom)

    result = asyncio.run(service.get_user_strategies(user))

    assert len(result) == 1
    assert result[0].portfolio == []
    assert result[0].account_deleted is False
