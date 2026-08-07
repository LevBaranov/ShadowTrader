"""Тесты настроек расчёта: комиссия у брокера, delta/min_lots_to_keep у стратегии.

Проверяем валидацию единиц (доля, а не проценты) и то, что настройки доезжают
до расчёта — раньше все три значения были общими и жили в toml.
"""
import asyncio
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.core.broker_service import (
    BrokerNotFoundError,
    BrokerService,
    BrokerValidationError,
)
from src.core.strategy_service import (
    StrategyNotFoundError,
    StrategyService,
    StrategyValidationError,
)
from src.models.balancer_params import BalancerParams
from src.models.broker_names import BrokerNames
from src.models.strategies_type import StrategiesType


class FakeBrokerRepo:
    def __init__(self):
        self.brokers = {}
        self.upserted = None

    async def upsert(self, user_id, broker_name, encrypted_token, sandbox, commission=None):
        broker = SimpleNamespace(
            id=uuid.uuid4(),
            user_id=user_id,
            broker_name=broker_name,
            broker_token=encrypted_token,
            sandbox=sandbox,
            commission=commission if commission is not None else Decimal("0.003"),
        )
        self.upserted = commission
        self.brokers[broker.id] = broker
        return broker

    async def update_commission(self, broker_id, user_id, commission):
        broker = self.brokers.get(broker_id)
        if broker is None or broker.user_id != user_id:
            return None
        broker.commission = commission
        return broker


class FakeBrokerClient:
    def __init__(self, token=None, sandbox=None):
        pass

    def get_all_accounts(self):
        return []


@pytest.fixture
def user():
    return SimpleNamespace(id=uuid.uuid4())


@pytest.fixture
def broker_repo():
    return FakeBrokerRepo()


@pytest.fixture
def broker_service(broker_repo, monkeypatch):
    # Токен шифруется реальным crypto — ключ в окружении выставляет conftest.
    return BrokerService(
        broker_repo=broker_repo,
        accounts_repo=None,
        broker_client_factory=FakeBrokerClient,
    )


class TestBrokerCommission:

    def _save(self, service, user, commission):
        return asyncio.run(
            service.save_broker_settings(
                user=user,
                broker_name=BrokerNames.T_BANK,
                token="t.token",
                sandbox=False,
                commission=commission,
            )
        )

    def test_default_when_not_passed(self, broker_service, user, broker_repo):
        broker = self._save(broker_service, user, None)

        assert broker.commission == Decimal("0.003")
        # None до репозитория доходит как «не менять».
        assert broker_repo.upserted is None

    def test_saves_fraction(self, broker_service, user):
        broker = self._save(broker_service, user, Decimal("0.0005"))

        assert broker.commission == Decimal("0.0005")

    def test_zero_is_allowed(self, broker_service, user):
        assert self._save(broker_service, user, Decimal("0")).commission == Decimal("0")

    @pytest.mark.parametrize("value", ["1", "3", "-0.001"])
    def test_rejects_non_fraction(self, broker_service, user, value):
        """0.3 или 3 вместо 0.003 — проценты вместо доли."""
        with pytest.raises(BrokerValidationError):
            self._save(broker_service, user, Decimal(value))

    def test_update_commission(self, broker_service, user):
        broker = self._save(broker_service, user, None)

        updated = asyncio.run(
            broker_service.update_commission(user, broker.id, Decimal("0.01"))
        )

        assert updated.commission == Decimal("0.01")

    def test_update_foreign_broker_raises(self, broker_service, user):
        broker = self._save(broker_service, user, None)
        other_user = SimpleNamespace(id=uuid.uuid4())

        with pytest.raises(BrokerNotFoundError):
            asyncio.run(
                broker_service.update_commission(other_user, broker.id, Decimal("0.01"))
            )

    def test_update_validates_range(self, broker_service, user):
        broker = self._save(broker_service, user, None)

        with pytest.raises(BrokerValidationError):
            asyncio.run(
                broker_service.update_commission(user, broker.id, Decimal("1.5"))
            )


class FakeStrategyRepo:
    def __init__(self):
        self.strategies = {}

    async def exists_for_account(self, brokers_account_id):
        return False

    async def create(self, user_id, strategy_type, brokers_account_id,
                     stock_markets_index_id, max_cash=0, delta=None,
                     min_lots_to_keep=None):
        strategy = SimpleNamespace(
            id=uuid.uuid4(),
            user_id=user_id,
            strategy_type=strategy_type,
            brokers_account_id=brokers_account_id,
            stock_markets_index_id=stock_markets_index_id,
            max_cash=max_cash,
            delta=Decimal("0.05") if delta is None else delta,
            min_lots_to_keep=1 if min_lots_to_keep is None else min_lots_to_keep,
        )
        self.strategies[strategy.id] = strategy
        return strategy

    async def update_settings(self, user_id, strategy_id, max_cash, delta,
                              min_lots_to_keep):
        strategy = self.strategies.get(strategy_id)
        if strategy is None or strategy.user_id != user_id:
            return None
        strategy.max_cash = max_cash
        strategy.delta = delta
        strategy.min_lots_to_keep = min_lots_to_keep
        return strategy


class FakeAccountsRepo:
    async def get_for_user(self, account_id, user_id):
        return SimpleNamespace(id=account_id)


class FakeIndexRepo:
    async def get_by_id(self, index_id):
        return SimpleNamespace(id=index_id)


@pytest.fixture
def strategy_repo():
    return FakeStrategyRepo()


@pytest.fixture
def strategy_service(strategy_repo):
    return StrategyService(
        strategy_repo=strategy_repo,
        accounts_repo=FakeAccountsRepo(),
        index_repo=FakeIndexRepo(),
    )


class TestStrategySettings:

    def _create(self, service, user, **kwargs):
        return asyncio.run(
            service.create_strategy(
                user=user,
                brokers_account_id=uuid.uuid4(),
                stock_markets_index_id=uuid.uuid4(),
                strategy_type=StrategiesType.SHARE,
                **kwargs,
            )
        )

    def test_defaults(self, strategy_service, user):
        strategy = self._create(strategy_service, user)

        assert strategy.delta == Decimal("0.05")
        assert strategy.min_lots_to_keep == 1
        assert strategy.max_cash == 0

    def test_custom_settings(self, strategy_service, user):
        strategy = self._create(
            strategy_service, user,
            max_cash=5000, delta=Decimal("0.02"), min_lots_to_keep=3,
        )

        assert strategy.max_cash == 5000
        assert strategy.delta == Decimal("0.02")
        assert strategy.min_lots_to_keep == 3

    @pytest.mark.parametrize("delta", ["1", "5", "-0.01"])
    def test_rejects_delta_as_percent(self, strategy_service, user, delta):
        with pytest.raises(StrategyValidationError):
            self._create(strategy_service, user, delta=Decimal(delta))

    def test_rejects_negative_min_lots(self, strategy_service, user):
        with pytest.raises(StrategyValidationError):
            self._create(strategy_service, user, min_lots_to_keep=-1)

    def test_update_settings(self, strategy_service, user):
        strategy = self._create(strategy_service, user)

        updated = asyncio.run(
            strategy_service.update_settings(
                user, strategy.id,
                max_cash=1000, delta=Decimal("0.07"), min_lots_to_keep=2,
            )
        )

        assert (updated.max_cash, updated.delta, updated.min_lots_to_keep) == (
            1000, Decimal("0.07"), 2
        )

    def test_update_foreign_strategy_raises(self, strategy_service, user):
        strategy = self._create(strategy_service, user)
        other_user = SimpleNamespace(id=uuid.uuid4())

        with pytest.raises(StrategyNotFoundError):
            asyncio.run(
                strategy_service.update_settings(
                    other_user, strategy.id,
                    max_cash=0, delta=Decimal("0.05"), min_lots_to_keep=1,
                )
            )

    def test_update_validates_delta(self, strategy_service, user):
        strategy = self._create(strategy_service, user)

        with pytest.raises(StrategyValidationError):
            asyncio.run(
                strategy_service.update_settings(
                    user, strategy.id,
                    max_cash=0, delta=Decimal("10"), min_lots_to_keep=1,
                )
            )


class TestBalancerParamsFromStrategy:
    """Комиссия берётся с брокера счёта, остальное — со стратегии."""

    @staticmethod
    def _strategy(commission="0.003", delta="0.05", min_lots=1, max_cash=0):
        return SimpleNamespace(
            max_cash=max_cash,
            delta=Decimal(delta),
            min_lots_to_keep=min_lots,
            brokers_account=SimpleNamespace(
                users_broker=SimpleNamespace(commission=Decimal(commission))
            ),
        )

    def test_collects_from_owners(self):
        params = BalancerParams.from_strategy(
            self._strategy(commission="0.01", delta="0.03", min_lots=2, max_cash=500)
        )

        assert params.commission == Decimal("0.01")
        assert params.delta == Decimal("0.03")
        assert params.min_lots_to_keep == 2
        assert params.max_cash == 500

    def test_two_brokers_give_different_commission(self):
        """У двух брокеров разные тарифы — расчёт по каждой стратегии свой."""
        cheap = BalancerParams.from_strategy(self._strategy(commission="0.0004"))
        pricey = BalancerParams.from_strategy(self._strategy(commission="0.003"))

        assert cheap.commission != pricey.commission
