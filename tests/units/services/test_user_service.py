"""Тесты UserService: стратегия по счёту, пропавшему у брокера, показывается неактивной."""
import asyncio
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.core.user_service import AccountDeletedError, UserService
from src.services.broker import BrokerAccountNotFoundError


class FakeStrategyRepo:
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

    def calculate_rebalance(self, index_name, params):
        raise BrokerAccountNotFoundError("Account not found in broker")


def make_strategy(deleted_at=None):
    users_broker = SimpleNamespace(
        id=uuid.uuid4(),
        broker_name="T-Bank",
        broker_token="encrypted",
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
    strategy = make_strategy()
    service = make_service(monkeypatch, [strategy])

    with pytest.raises(AccountDeletedError):
        asyncio.run(service.execute_strategy_rebalance(user, strategy.id))
