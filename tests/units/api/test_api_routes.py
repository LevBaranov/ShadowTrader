"""Тесты API-роутов.

Роуты тестируются через TestClient с подменой зависимостей (сервисы и
текущий пользователь мокаются) — проверяем коды ответов, сериализацию
и маппинг доменных ошибок в HTTP.
"""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies.auth import get_current_user
from src.api.dependencies.broker import get_broker_service
from src.api.dependencies.strategy import get_strategy_service, get_strategy_manager
from src.core.broker_service import BrokerNotFoundError
from src.core.strategy_service import StrategyValidationError, StrategyNotFoundError
from src.core.user_service import (
    StrategyNotFoundError as UserStrategyNotFoundError,
    AccountDeletedError,
)
from src.services.broker import BrokerAuthError
from src.models.api_user import BrokerInfoStrategy, UserStrategy, BaseInfo
from src.models.broker_names import BrokerNames
from src.models.rebalance import (
    PortfolioPosition,
    RebalanceResult,
    RebalanceActionResult,
    RebalanceErrorResult,
)
from src.models.stock_markets_name import StockMarketsNames
from src.models.strategies_type import StrategiesType


@pytest.fixture
def fake_user():
    return SimpleNamespace(id=uuid.uuid4(), email="user@example.com")


@pytest.fixture
def user_service():
    return MagicMock()


@pytest.fixture
def strategy_service():
    return MagicMock()


@pytest.fixture
def broker_service():
    return MagicMock()


@pytest.fixture
def client(fake_user, user_service, strategy_service, broker_service):
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_strategy_service] = lambda: user_service
    app.dependency_overrides[get_strategy_manager] = lambda: strategy_service
    app.dependency_overrides[get_broker_service] = lambda: broker_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def make_user_strategy(**overrides) -> UserStrategy:
    fields = dict(
        id=str(uuid.uuid4()),
        broker_info=BrokerInfoStrategy(
            id=str(uuid.uuid4()),
            name="T-Bank",
            account=BaseInfo(id="acc-1", name="Основной"),
        ),
        index_info=BaseInfo(id=str(uuid.uuid4()), name="IMOEX"),
        portfolio=[
            PortfolioPosition(
                ticker="SBER",
                name="Сбербанк",
                uid="uid-1",
                index_weight=3.5,
                portfolio_weight=5.0,
                portfolio_count=10,
                offer=-3,
            )
        ],
        free_cash=100.5,
        free_cash_after=20.25,
        account_deleted=False,
    )
    fields.update(overrides)
    return UserStrategy(**fields)


class TestHealth:

    def test_health(self, client):
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestLogin:

    @pytest.fixture
    def anon_client(self):
        from src.db.database import get_session

        app = create_app()
        app.dependency_overrides[get_session] = lambda: MagicMock()

        with TestClient(app) as test_client:
            yield test_client

        app.dependency_overrides.clear()

    @staticmethod
    def _patch_user_repo(monkeypatch, user):
        repo = MagicMock()
        repo.get_user_by_email = AsyncMock(return_value=user)
        monkeypatch.setattr("src.api.routes.auth.UserRepository", lambda db: repo)
        return repo

    def test_login_success(self, anon_client, monkeypatch):
        from src.api.security import hash_password

        user = SimpleNamespace(id=uuid.uuid4(), password_hash=hash_password("secret"))
        self._patch_user_repo(monkeypatch, user)

        response = anon_client.post(
            "/auth/login", json={"email": "user@example.com", "password": "secret"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["tokenType"] == "bearer"
        assert body["accessToken"]

    def test_login_wrong_password(self, anon_client, monkeypatch):
        from src.api.security import hash_password

        user = SimpleNamespace(id=uuid.uuid4(), password_hash=hash_password("secret"))
        self._patch_user_repo(monkeypatch, user)

        response = anon_client.post(
            "/auth/login", json={"email": "user@example.com", "password": "wrong"}
        )

        assert response.status_code == 401

    def test_login_unknown_user(self, anon_client, monkeypatch):
        self._patch_user_repo(monkeypatch, None)

        response = anon_client.post(
            "/auth/login", json={"email": "nobody@example.com", "password": "secret"}
        )

        assert response.status_code == 401


class TestAuthRequired:
    """Все защищённые роуты без токена должны отдавать 401 (HTTPBearer)."""

    @pytest.mark.parametrize("method, path", [
        ("GET", "/users/me"),
        ("POST", "/portfolios/balance"),
        ("GET", "/brokers"),
        ("PUT", "/brokers"),
        ("GET", f"/brokers/{uuid.uuid4()}/accounts"),
        ("POST", f"/brokers/{uuid.uuid4()}/accounts/refresh"),
        ("GET", "/indices"),
        ("POST", "/strategies"),
        ("DELETE", f"/strategies/{uuid.uuid4()}"),
    ])
    def test_requires_auth(self, method, path):
        app = create_app()
        with TestClient(app) as client:
            response = client.request(method, path)

        assert response.status_code == 401

    def test_invalid_token(self):
        app = create_app()
        with TestClient(app) as client:
            response = client.get(
                "/users/me", headers={"Authorization": "Bearer not-a-jwt"}
            )

        assert response.status_code == 401


class TestGetMe:

    def test_returns_user_with_strategies(self, client, user_service, fake_user):
        user_service.get_user_strategies = AsyncMock(
            return_value=[make_user_strategy()]
        )

        response = client.get("/users/me")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(fake_user.id)
        assert body["email"] == fake_user.email

        strategy = body["strategies"][0]
        assert strategy["freeCash"] == 100.5
        assert strategy["freeCashAfter"] == 20.25
        assert strategy["accountDeleted"] is False
        assert strategy["brokerInfo"]["account"]["name"] == "Основной"
        # Отрицательный offer означает продажу.
        assert strategy["portfolio"][0]["offer"] == -3

    def test_marks_deleted_account(self, client, user_service):
        user_service.get_user_strategies = AsyncMock(
            return_value=[
                make_user_strategy(
                    portfolio=[], free_cash=0.0, free_cash_after=0.0,
                    account_deleted=True,
                )
            ]
        )

        response = client.get("/users/me")

        assert response.status_code == 200
        strategy = response.json()["strategies"][0]
        assert strategy["accountDeleted"] is True
        assert strategy["portfolio"] == []
        assert strategy["freeCash"] == 0.0


class TestBalance:

    def test_success(self, client, user_service, fake_user):
        strategy_id = str(uuid.uuid4())
        user_service.execute_strategy_rebalance = AsyncMock(
            return_value=RebalanceResult(
                success=[
                    RebalanceActionResult(type="BUY", ticker="SBER", quantity=5)
                ],
                errors=[
                    RebalanceErrorResult(
                        type="SELL", ticker="GAZP", quantity=2,
                        description="Недостаточно активов",
                    )
                ],
            )
        )

        response = client.post(
            "/portfolios/balance", json={"strategyId": strategy_id}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"][0] == {
            "type": "BUY", "ticker": "SBER", "quantity": 5,
        }
        assert body["errors"][0]["description"] == "Недостаточно активов"

        user_service.execute_strategy_rebalance.assert_awaited_once_with(
            fake_user, strategy_id
        )

    def test_accepts_snake_case_body(self, client, user_service):
        user_service.execute_strategy_rebalance = AsyncMock(
            return_value=RebalanceResult(success=[], errors=[])
        )

        response = client.post(
            "/portfolios/balance", json={"strategy_id": str(uuid.uuid4())}
        )

        assert response.status_code == 200

    def test_strategy_not_found(self, client, user_service):
        user_service.execute_strategy_rebalance = AsyncMock(
            side_effect=UserStrategyNotFoundError("not found")
        )

        response = client.post(
            "/portfolios/balance", json={"strategyId": str(uuid.uuid4())}
        )

        assert response.status_code == 404

    def test_deleted_account(self, client, user_service):
        user_service.execute_strategy_rebalance = AsyncMock(
            side_effect=AccountDeletedError("deleted")
        )

        response = client.post(
            "/portfolios/balance", json={"strategyId": str(uuid.uuid4())}
        )

        assert response.status_code == 422
        assert "удалённым" in response.json()["detail"]

    def test_body_required(self, client):
        response = client.post("/portfolios/balance", json={})

        assert response.status_code == 422


class TestSaveBroker:

    def test_success(self, client, broker_service, fake_user):
        broker = SimpleNamespace(
            id=uuid.uuid4(), broker_name=BrokerNames.T_BANK, sandbox=False
        )
        broker_service.save_broker_settings = AsyncMock(return_value=broker)

        response = client.put(
            "/brokers", json={"brokerName": "T-Bank", "token": "t.token"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(broker.id)
        assert body["brokerName"] == "T-Bank"
        assert body["sandbox"] is False
        # Токен наружу не возвращается.
        assert "token" not in body

        broker_service.save_broker_settings.assert_awaited_once_with(
            user=fake_user,
            broker_name=BrokerNames.T_BANK,
            token="t.token",
            sandbox=False,
        )

    def test_invalid_token(self, client, broker_service):
        broker_service.save_broker_settings = AsyncMock(
            side_effect=BrokerAuthError("invalid")
        )

        response = client.put(
            "/brokers", json={"brokerName": "T-Bank", "token": "bad"}
        )

        assert response.status_code == 422
        assert response.json()["detail"] == "Токен брокера недействителен"

    def test_unknown_broker_name(self, client):
        response = client.put(
            "/brokers", json={"brokerName": "NoSuchBroker", "token": "t"}
        )

        assert response.status_code == 422


class TestListBrokers:

    def test_success(self, client, broker_service):
        brokers = [
            SimpleNamespace(
                id=uuid.uuid4(), broker_name=BrokerNames.T_BANK, sandbox=True
            )
        ]
        broker_service.list_brokers = AsyncMock(return_value=brokers)

        response = client.get("/brokers")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["brokerName"] == "T-Bank"
        assert body[0]["sandbox"] is True

    def test_empty(self, client, broker_service):
        broker_service.list_brokers = AsyncMock(return_value=[])

        response = client.get("/brokers")

        assert response.status_code == 200
        assert response.json() == []


class TestBrokerAccounts:

    @pytest.fixture
    def accounts(self):
        return [
            SimpleNamespace(
                id=uuid.uuid4(), account_id="b-1", account_name="Основной"
            ),
            SimpleNamespace(
                id=uuid.uuid4(), account_id="b-2", account_name=""
            ),
        ]

    def test_get_accounts_with_busy_flag(self, client, broker_service, accounts):
        broker_service.get_broker_accounts = AsyncMock(return_value=accounts)
        broker_service.get_busy_account_ids = AsyncMock(
            return_value={accounts[1].id}
        )

        response = client.get(f"/brokers/{uuid.uuid4()}/accounts")

        assert response.status_code == 200
        body = response.json()
        assert body[0]["hasStrategy"] is False
        assert body[1]["hasStrategy"] is True
        assert body[1]["accountName"] == ""

    def test_get_accounts_broker_not_found(self, client, broker_service):
        broker_service.get_broker_accounts = AsyncMock(
            side_effect=BrokerNotFoundError("nope")
        )

        response = client.get(f"/brokers/{uuid.uuid4()}/accounts")

        assert response.status_code == 404

    def test_get_accounts_invalid_broker_token(self, client, broker_service):
        broker_service.get_broker_accounts = AsyncMock(
            side_effect=BrokerAuthError("invalid")
        )

        response = client.get(f"/brokers/{uuid.uuid4()}/accounts")

        assert response.status_code == 422

    def test_refresh_accounts(self, client, broker_service, accounts, fake_user):
        broker_id = uuid.uuid4()
        broker_service.refresh_broker_accounts = AsyncMock(return_value=accounts)
        broker_service.get_busy_account_ids = AsyncMock(return_value=set())

        response = client.post(f"/brokers/{broker_id}/accounts/refresh")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        assert all(item["hasStrategy"] is False for item in body)

        broker_service.refresh_broker_accounts.assert_awaited_once_with(
            fake_user, broker_id
        )

    def test_refresh_accounts_broker_not_found(self, client, broker_service):
        broker_service.refresh_broker_accounts = AsyncMock(
            side_effect=BrokerNotFoundError("nope")
        )

        response = client.post(f"/brokers/{uuid.uuid4()}/accounts/refresh")

        assert response.status_code == 404

    def test_refresh_accounts_invalid_token(self, client, broker_service):
        broker_service.refresh_broker_accounts = AsyncMock(
            side_effect=BrokerAuthError("invalid")
        )

        response = client.post(f"/brokers/{uuid.uuid4()}/accounts/refresh")

        assert response.status_code == 422


class TestIndices:

    def test_success(self, client, strategy_service):
        index = SimpleNamespace(
            id=uuid.uuid4(),
            stock_market=StockMarketsNames.MOEX,
            index_name="IMOEX",
            description="Индекс МосБиржи",
        )
        strategy_service.list_indices = AsyncMock(return_value=[index])

        response = client.get("/indices")

        assert response.status_code == 200
        body = response.json()
        assert body == [{
            "id": str(index.id),
            "stockMarket": "MOEX",
            "indexName": "IMOEX",
            "description": "Индекс МосБиржи",
        }]


class TestCreateStrategy:

    def test_success(self, client, strategy_service, fake_user):
        strategy_id = uuid.uuid4()
        account_id = uuid.uuid4()
        index_id = uuid.uuid4()
        strategy_service.create_strategy = AsyncMock(
            return_value=SimpleNamespace(
                id=strategy_id,
                brokers_account_id=account_id,
                stock_markets_index_id=index_id,
                strategy_type=StrategiesType.SHARE,
            )
        )

        response = client.post("/strategies", json={
            "brokersAccountId": str(account_id),
            "stockMarketsIndexId": str(index_id),
        })

        assert response.status_code == 201
        body = response.json()
        assert body["id"] == str(strategy_id)
        assert body["brokersAccountId"] == str(account_id)
        assert body["stockMarketsIndexId"] == str(index_id)

        strategy_service.create_strategy.assert_awaited_once_with(
            user=fake_user,
            brokers_account_id=account_id,
            stock_markets_index_id=index_id,
            strategy_type=StrategiesType.SHARE,
        )

    def test_busy_account(self, client, strategy_service):
        strategy_service.create_strategy = AsyncMock(
            side_effect=StrategyValidationError("На этом счёте уже есть стратегия")
        )

        response = client.post("/strategies", json={
            "brokersAccountId": str(uuid.uuid4()),
            "stockMarketsIndexId": str(uuid.uuid4()),
        })

        assert response.status_code == 422
        assert response.json()["detail"] == "На этом счёте уже есть стратегия"

    def test_invalid_uuid(self, client, strategy_service):
        response = client.post("/strategies", json={
            "brokersAccountId": "not-a-uuid",
            "stockMarketsIndexId": str(uuid.uuid4()),
        })

        assert response.status_code == 422

    def test_body_required(self, client):
        response = client.post("/strategies", json={})

        assert response.status_code == 422


class TestDeleteStrategy:

    def test_success(self, client, strategy_service, fake_user):
        strategy_id = uuid.uuid4()
        strategy_service.delete_strategy = AsyncMock(return_value=None)

        response = client.delete(f"/strategies/{strategy_id}")

        assert response.status_code == 204
        strategy_service.delete_strategy.assert_awaited_once_with(
            fake_user, strategy_id
        )

    def test_not_found(self, client, strategy_service):
        strategy_service.delete_strategy = AsyncMock(
            side_effect=StrategyNotFoundError("nope")
        )

        response = client.delete(f"/strategies/{uuid.uuid4()}")

        assert response.status_code == 404

    def test_invalid_uuid_in_path(self, client):
        response = client.delete("/strategies/not-a-uuid")

        assert response.status_code == 422
