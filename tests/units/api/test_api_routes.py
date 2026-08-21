"""Тесты API-роутов.

Роуты тестируются через TestClient с подменой зависимостей (сервисы и
текущий пользователь мокаются) — проверяем коды ответов, сериализацию
и маппинг доменных ошибок в HTTP.
"""
import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies.auth import get_current_user
from src.api.dependencies.broker import get_broker_service
from src.api.dependencies.registration import get_registration_service
from src.api.dependencies.strategy import get_strategy_service, get_strategy_manager
from src.api.dependencies.telegram_link import get_telegram_link_service
from src.api.dependencies.task import get_task_service
from src.api.dependencies.bond import get_bond_service
from src.core.broker_service import BrokerNotFoundError
from src.core.task_service import (
    TaskValidationError,
    TaskAlreadyExistsError,
    TaskNotFoundError,
)
from src.core.registration_service import (
    EmailAlreadyRegisteredError,
    InvalidCodeError,
    ResendCooldownError,
    TooManyAttemptsError,
)
from src.core.telegram_link_service import (
    TelegramNotLinkedError,
    TelegramAlreadyLinkedError,
    LinkCodeInvalidError,
    LastLoginMethodError,
)
from src.core.strategy_service import StrategyValidationError, StrategyNotFoundError
from src.core.user_service import (
    StrategyNotFoundError as UserStrategyNotFoundError,
    AccountDeletedError,
)
from src.core.bond_service import AccountNotFoundError
from src.core.notification_settings_service import NotificationChannelUnavailableError
from src.core.email_change_service import (
    EmailAlreadyTakenError,
    EmailUnchangedError,
    NoPendingEmailError,
    PasswordRequiredError,
)
from src.core.verification import CodeExpiredError
from src.services.broker import BrokerAuthError
from src.models.api_user import (
    BaseInfo,
    BrokerInfoStrategy,
    StrategySettings,
    UserStrategy,
)
from src.models.bond import BondEvent, BondEventType
from src.models.broker_names import BrokerNames
from src.models.notification_channel import NotificationChannel
from src.models.rebalance import (
    PortfolioPosition,
    RebalanceResult,
    RebalanceActionResult,
    RebalanceErrorResult,
)
from src.models.scheduler_frequency import ScheduleFrequency
from src.models.stock_markets_name import StockMarketsNames
from src.models.strategies_type import StrategiesType


@pytest.fixture
def fake_user():
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="user@example.com",
        pending_email=None,
        telegram_id=None,
        notification_channel=NotificationChannel.EMAIL,
    )


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
def registration_service():
    return AsyncMock()


@pytest.fixture
def telegram_link_service():
    return AsyncMock()


@pytest.fixture
def task_service():
    return AsyncMock()


@pytest.fixture
def bond_service():
    return AsyncMock()


@pytest.fixture
def email_change_service():
    return AsyncMock()


@pytest.fixture
def notification_settings_service():
    return AsyncMock()


@pytest.fixture
def client(fake_user, user_service, strategy_service, broker_service, registration_service,
           telegram_link_service, task_service, bond_service):
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_strategy_service] = lambda: user_service
    app.dependency_overrides[get_strategy_manager] = lambda: strategy_service
    app.dependency_overrides[get_broker_service] = lambda: broker_service
    app.dependency_overrides[get_registration_service] = lambda: registration_service
    app.dependency_overrides[get_telegram_link_service] = lambda: telegram_link_service
    app.dependency_overrides[get_task_service] = lambda: task_service
    app.dependency_overrides[get_bond_service] = lambda: bond_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def make_broker(broker_id=None, sandbox=False, commission="0.003"):
    """ORM-брокер так, как его видят роуты после сервиса."""
    return SimpleNamespace(
        id=broker_id or uuid.uuid4(),
        broker_name=BrokerNames.T_BANK,
        sandbox=sandbox,
        commission=Decimal(commission),
    )


def make_user_strategy(**overrides) -> UserStrategy:
    fields = dict(
        id=str(uuid.uuid4()),
        broker_info=BrokerInfoStrategy(
            id=str(uuid.uuid4()),
            name="T-Bank",
            account=BaseInfo(id="acc-1", name="Основной"),
            commission=Decimal("0.003"),
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
        settings=StrategySettings(
            max_cash=0, delta=Decimal("0.05"), min_lots_to_keep=1
        ),
        account_deleted=False,
    )
    fields.update(overrides)
    return UserStrategy(**fields)


def make_strategy_entity(
    strategy_id=None,
    account_id=None,
    index_id=None,
    max_cash=0,
    delta="0.05",
    min_lots_to_keep=1,
):
    """ORM-стратегия так, как её видят роуты после сервиса."""
    return SimpleNamespace(
        id=strategy_id or uuid.uuid4(),
        brokers_account_id=account_id or uuid.uuid4(),
        stock_markets_index_id=index_id or uuid.uuid4(),
        strategy_type=StrategiesType.SHARE,
        max_cash=max_cash,
        delta=Decimal(delta),
        min_lots_to_keep=min_lots_to_keep,
    )


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
    def _patch_identity_repo(monkeypatch, identity):
        repo = MagicMock()
        repo.get_by_provider_external_id = AsyncMock(return_value=identity)
        monkeypatch.setattr("src.api.routes.auth.AuthIdentityRepository", lambda db: repo)
        return repo

    def test_login_success(self, anon_client, monkeypatch):
        from src.api.security import hash_password
        from src.core.registration_service import _utcnow

        identity = SimpleNamespace(
            user_id=uuid.uuid4(),
            password_hash=hash_password("secret"),
            verified_at=_utcnow(),
        )
        self._patch_identity_repo(monkeypatch, identity)

        response = anon_client.post(
            "/auth/login", json={"email": "user@example.com", "password": "secret"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["tokenType"] == "bearer"
        assert body["accessToken"]

    def test_login_unverified_email(self, anon_client, monkeypatch):
        from src.api.security import hash_password

        identity = SimpleNamespace(
            user_id=uuid.uuid4(),
            password_hash=hash_password("secret"),
            verified_at=None,
        )
        self._patch_identity_repo(monkeypatch, identity)

        response = anon_client.post(
            "/auth/login", json={"email": "user@example.com", "password": "secret"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "email_not_verified"

    def test_login_wrong_password(self, anon_client, monkeypatch):
        from src.api.security import hash_password

        identity = SimpleNamespace(
            user_id=uuid.uuid4(), password_hash=hash_password("secret")
        )
        self._patch_identity_repo(monkeypatch, identity)

        response = anon_client.post(
            "/auth/login", json={"email": "user@example.com", "password": "wrong"}
        )

        assert response.status_code == 401

    def test_login_unknown_user(self, anon_client, monkeypatch):
        self._patch_identity_repo(monkeypatch, None)

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
        ("PATCH", f"/brokers/{uuid.uuid4()}"),
        ("GET", f"/brokers/{uuid.uuid4()}/accounts"),
        ("POST", f"/brokers/{uuid.uuid4()}/accounts/refresh"),
        ("GET", "/indices"),
        ("POST", "/strategies"),
        ("PATCH", f"/strategies/{uuid.uuid4()}"),
        ("DELETE", f"/strategies/{uuid.uuid4()}"),
        ("GET", "/accounts"),
        ("POST", "/accounts/refresh"),
        ("GET", f"/bonds/events?brokersAccountId={uuid.uuid4()}"),
        ("GET", "/tasks"),
        ("POST", "/tasks"),
        ("PATCH", f"/tasks/{uuid.uuid4()}"),
        ("DELETE", f"/tasks/{uuid.uuid4()}"),
        ("GET", "/users/me/profile"),
        ("PATCH", "/users/me/notifications"),
        ("POST", "/users/me/email"),
        ("POST", "/users/me/email/confirm"),
        ("POST", "/users/me/email/resend"),
        ("DELETE", "/users/me/email/pending"),
        ("POST", "/users/me/telegram-link"),
        ("DELETE", "/users/me/telegram-link"),
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
        broker = make_broker()
        broker_service.save_broker_settings = AsyncMock(return_value=broker)

        response = client.put(
            "/brokers", json={"brokerName": "T-Bank", "token": "t.token"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(broker.id)
        assert body["brokerName"] == "T-Bank"
        assert body["sandbox"] is False
        # Комиссия — доля, а не проценты.
        assert body["commission"] == "0.003"
        # Токен наружу не возвращается.
        assert "token" not in body

        broker_service.save_broker_settings.assert_awaited_once_with(
            user=fake_user,
            broker_name=BrokerNames.T_BANK,
            token="t.token",
            sandbox=False,
            commission=None,
        )

    def test_success_with_commission(self, client, broker_service):
        broker_service.save_broker_settings = AsyncMock(
            return_value=make_broker(commission="0.0005")
        )

        response = client.put(
            "/brokers",
            json={"brokerName": "T-Bank", "token": "t.token", "commission": "0.0005"},
        )

        assert response.status_code == 200
        assert response.json()["commission"] == "0.0005"
        assert broker_service.save_broker_settings.await_args.kwargs["commission"] == (
            Decimal("0.0005")
        )

    def test_commission_as_percent_rejected(self, client, broker_service):
        """0.3 вместо 0.003 — типичная ошибка, ловим на границе контракта."""
        response = client.put(
            "/brokers",
            json={"brokerName": "T-Bank", "token": "t.token", "commission": "3"},
        )

        assert response.status_code == 422

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
        broker_service.list_brokers = AsyncMock(
            return_value=[make_broker(sandbox=True, commission="0.01")]
        )

        response = client.get("/brokers")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["brokerName"] == "T-Bank"
        assert body[0]["sandbox"] is True
        assert body[0]["commission"] == "0.01"

    def test_empty(self, client, broker_service):
        broker_service.list_brokers = AsyncMock(return_value=[])

        response = client.get("/brokers")

        assert response.status_code == 200
        assert response.json() == []


class TestUpdateBroker:
    """Комиссия по тарифу — правится без токена (PATCH /brokers/{id})."""

    def test_success(self, client, broker_service, fake_user):
        broker_id = uuid.uuid4()
        broker_service.update_commission = AsyncMock(
            return_value=make_broker(broker_id=broker_id, commission="0.0004")
        )

        response = client.patch(f"/brokers/{broker_id}", json={"commission": "0.0004"})

        assert response.status_code == 200
        assert response.json()["commission"] == "0.0004"
        broker_service.update_commission.assert_awaited_once_with(
            fake_user, broker_id, Decimal("0.0004")
        )

    def test_not_found(self, client, broker_service):
        broker_service.update_commission = AsyncMock(
            side_effect=BrokerNotFoundError("nope")
        )

        response = client.patch(f"/brokers/{uuid.uuid4()}", json={"commission": "0.003"})

        assert response.status_code == 404

    def test_commission_out_of_range(self, client, broker_service):
        response = client.patch(f"/brokers/{uuid.uuid4()}", json={"commission": "1.5"})

        assert response.status_code == 422

    def test_body_required(self, client, broker_service):
        response = client.patch(f"/brokers/{uuid.uuid4()}", json={})

        assert response.status_code == 422


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
            return_value=make_strategy_entity(
                strategy_id=strategy_id, account_id=account_id, index_id=index_id
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
        assert body["maxCash"] == 0
        assert body["delta"] == "0.05"
        assert body["minLotsToKeep"] == 1

        strategy_service.create_strategy.assert_awaited_once_with(
            user=fake_user,
            brokers_account_id=account_id,
            stock_markets_index_id=index_id,
            strategy_type=StrategiesType.SHARE,
            max_cash=0,
            # Не заданы в теле — сервис оставит значения по умолчанию из БД.
            delta=None,
            min_lots_to_keep=None,
        )

    def test_with_settings(self, client, strategy_service):
        account_id = uuid.uuid4()
        index_id = uuid.uuid4()
        strategy_service.create_strategy = AsyncMock(
            return_value=make_strategy_entity(
                account_id=account_id, index_id=index_id,
                delta="0.1", min_lots_to_keep=2,
            )
        )

        response = client.post("/strategies", json={
            "brokersAccountId": str(account_id),
            "stockMarketsIndexId": str(index_id),
            "delta": "0.1",
            "minLotsToKeep": 2,
        })

        assert response.status_code == 201
        body = response.json()
        assert body["delta"] == "0.1"
        assert body["minLotsToKeep"] == 2

        kwargs = strategy_service.create_strategy.await_args.kwargs
        assert kwargs["delta"] == Decimal("0.1")
        assert kwargs["min_lots_to_keep"] == 2

    def test_delta_as_percent_rejected(self, client, strategy_service):
        """5 вместо 0.05 — доля, а не проценты."""
        response = client.post("/strategies", json={
            "brokersAccountId": str(uuid.uuid4()),
            "stockMarketsIndexId": str(uuid.uuid4()),
            "delta": "5",
        })

        assert response.status_code == 422

    def test_with_max_cash(self, client, strategy_service, fake_user):
        account_id = uuid.uuid4()
        index_id = uuid.uuid4()
        strategy_service.create_strategy = AsyncMock(
            return_value=make_strategy_entity(
                account_id=account_id, index_id=index_id, max_cash=5000
            )
        )

        response = client.post("/strategies", json={
            "brokersAccountId": str(account_id),
            "stockMarketsIndexId": str(index_id),
            "maxCash": 5000,
        })

        assert response.status_code == 201
        assert response.json()["maxCash"] == 5000
        assert strategy_service.create_strategy.await_args.kwargs["max_cash"] == 5000

    def test_negative_max_cash(self, client, strategy_service):
        response = client.post("/strategies", json={
            "brokersAccountId": str(uuid.uuid4()),
            "stockMarketsIndexId": str(uuid.uuid4()),
            "maxCash": -1,
        })

        assert response.status_code == 422

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


class TestUpdateStrategy:
    """Настройки расчёта по стратегии (PATCH /strategies/{id}). Комиссии здесь нет."""

    SETTINGS = {"maxCash": 3000, "delta": "0.1", "minLotsToKeep": 2}

    def test_success(self, client, strategy_service, fake_user):
        strategy_id = uuid.uuid4()
        strategy_service.update_settings = AsyncMock(
            return_value=make_strategy_entity(
                strategy_id=strategy_id, max_cash=3000,
                delta="0.1", min_lots_to_keep=2,
            )
        )

        response = client.patch(f"/strategies/{strategy_id}", json=self.SETTINGS)

        assert response.status_code == 200
        body = response.json()
        assert body["maxCash"] == 3000
        assert body["delta"] == "0.1"
        assert body["minLotsToKeep"] == 2
        strategy_service.update_settings.assert_awaited_once_with(
            fake_user,
            strategy_id,
            max_cash=3000,
            delta=Decimal("0.1"),
            min_lots_to_keep=2,
        )

    def test_not_found(self, client, strategy_service):
        strategy_service.update_settings = AsyncMock(
            side_effect=StrategyNotFoundError("nope")
        )

        response = client.patch(f"/strategies/{uuid.uuid4()}", json=self.SETTINGS)

        assert response.status_code == 404

    def test_negative_value(self, client, strategy_service):
        response = client.patch(
            f"/strategies/{uuid.uuid4()}", json={**self.SETTINGS, "maxCash": -5}
        )

        assert response.status_code == 422

    def test_delta_as_percent_rejected(self, client, strategy_service):
        response = client.patch(
            f"/strategies/{uuid.uuid4()}", json={**self.SETTINGS, "delta": "10"}
        )

        assert response.status_code == 422

    def test_body_required(self, client, strategy_service):
        response = client.patch(f"/strategies/{uuid.uuid4()}", json={})

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


class TestRegister:

    def test_success(self, client, registration_service):
        response = client.post(
            "/auth/register",
            json={"email": "user@example.com", "password": "secret123"},
        )

        assert response.status_code == 201
        assert response.json() == {"email": "user@example.com"}
        registration_service.register.assert_awaited_once_with(
            "user@example.com", "secret123"
        )

    def test_email_already_registered(self, client, registration_service):
        registration_service.register.side_effect = EmailAlreadyRegisteredError("busy")

        response = client.post(
            "/auth/register",
            json={"email": "user@example.com", "password": "secret123"},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "email_already_registered"

    def test_short_password(self, client):
        response = client.post(
            "/auth/register",
            json={"email": "user@example.com", "password": "12345"},
        )

        assert response.status_code == 422

    def test_invalid_email(self, client):
        response = client.post(
            "/auth/register",
            json={"email": "not-an-email", "password": "secret123"},
        )

        assert response.status_code == 422


class TestConfirmEmail:

    def test_success_returns_token(self, client, registration_service):
        registration_service.confirm.return_value = SimpleNamespace(user_id=uuid.uuid4())

        response = client.post(
            "/auth/register/confirm",
            json={"email": "user@example.com", "code": "123456"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["accessToken"]
        assert body["tokenType"] == "bearer"

    def test_invalid_code(self, client, registration_service):
        registration_service.confirm.side_effect = InvalidCodeError("wrong")

        response = client.post(
            "/auth/register/confirm",
            json={"email": "user@example.com", "code": "000000"},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "invalid_code"

    def test_too_many_attempts(self, client, registration_service):
        registration_service.confirm.side_effect = TooManyAttemptsError("stop")

        response = client.post(
            "/auth/register/confirm",
            json={"email": "user@example.com", "code": "000000"},
        )

        assert response.status_code == 429


class TestResendCode:

    def test_success(self, client, registration_service):
        response = client.post(
            "/auth/register/resend",
            json={"email": "user@example.com"},
        )

        assert response.status_code == 200
        registration_service.resend_code.assert_awaited_once_with("user@example.com")

    def test_cooldown(self, client, registration_service):
        registration_service.resend_code.side_effect = ResendCooldownError("wait")

        response = client.post(
            "/auth/register/resend",
            json={"email": "user@example.com"},
        )

        assert response.status_code == 429


SERVICE_HEADERS = {"X-Service-Key": "test-bot-api-key"}


class TestServiceTelegram:

    def test_requires_service_key(self, client):
        response = client.post(
            "/service/telegram/token", json={"telegramId": 123456789}
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "invalid_service_key"

    def test_token_success(self, client, telegram_link_service):
        user_id = uuid.uuid4()
        telegram_link_service.get_linked_user_id.return_value = user_id

        response = client.post(
            "/service/telegram/token",
            json={"telegramId": 123456789},
            headers=SERVICE_HEADERS,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["accessToken"]
        assert body["tokenType"] == "bearer"
        assert body["expiresIn"] > 0
        telegram_link_service.get_linked_user_id.assert_awaited_once_with(123456789)

    def test_token_not_linked(self, client, telegram_link_service):
        telegram_link_service.get_linked_user_id.side_effect = TelegramNotLinkedError(1)

        response = client.post(
            "/service/telegram/token",
            json={"telegramId": 123456789},
            headers=SERVICE_HEADERS,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "telegram_not_linked"

    def test_register_success(self, client, telegram_link_service):
        telegram_link_service.register_telegram_user.return_value = SimpleNamespace(
            user_id=uuid.uuid4()
        )

        response = client.post(
            "/service/telegram/register",
            json={"telegramId": 123456789},
            headers=SERVICE_HEADERS,
        )

        assert response.status_code == 201
        assert response.json()["userId"]

    def test_register_already_linked(self, client, telegram_link_service):
        telegram_link_service.register_telegram_user.side_effect = (
            TelegramAlreadyLinkedError(1)
        )

        response = client.post(
            "/service/telegram/register",
            json={"telegramId": 123456789},
            headers=SERVICE_HEADERS,
        )

        assert response.status_code == 409

    def test_link_request_success(self, client, telegram_link_service):
        from src.core.verification import utcnow

        telegram_link_service.create_link_request.return_value = ("AB3F9K", utcnow())

        response = client.post(
            "/service/telegram/link-requests",
            json={"telegramId": 123456789},
            headers=SERVICE_HEADERS,
        )

        assert response.status_code == 200
        assert response.json()["code"] == "AB3F9K"


class TestTelegramLink:

    def test_confirm_success(self, client, telegram_link_service):
        telegram_link_service.confirm_link.return_value = 123456789

        response = client.post("/users/me/telegram-link", json={"code": "AB3F9K"})

        assert response.status_code == 200
        assert response.json()["telegramId"] == 123456789

    def test_confirm_invalid_code(self, client, telegram_link_service):
        telegram_link_service.confirm_link.side_effect = LinkCodeInvalidError("x")

        response = client.post("/users/me/telegram-link", json={"code": "WRONG1"})

        assert response.status_code == 400
        assert response.json()["detail"] == "invalid_code"

    def test_confirm_already_linked(self, client, telegram_link_service):
        telegram_link_service.confirm_link.side_effect = TelegramAlreadyLinkedError(1)

        response = client.post("/users/me/telegram-link", json={"code": "AB3F9K"})

        assert response.status_code == 409

    def test_unlink_success(self, client, telegram_link_service):
        telegram_link_service.unlink.return_value = None

        response = client.delete("/users/me/telegram-link")

        assert response.status_code == 204

    def test_unlink_last_login_method(self, client, telegram_link_service):
        telegram_link_service.unlink.side_effect = LastLoginMethodError(1)

        response = client.delete("/users/me/telegram-link")

        assert response.status_code == 409
        assert response.json()["detail"] == "last_login_method"

    def test_profile(self, client, fake_user):
        response = client.get("/users/me/profile")

        assert response.status_code == 200
        assert response.json() == {
            "email": "user@example.com",
            "pendingEmail": None,
            "telegramLinked": False,
            "notificationChannel": "EMAIL",
        }


class TestStrategiesList:

    def test_success(self, client, user_service):
        from src.models.api_user import StrategyListItem

        item = StrategyListItem(
            id=str(uuid.uuid4()),
            broker_info=BrokerInfoStrategy(
                id=str(uuid.uuid4()),
                name="T-Bank",
                account=BaseInfo(id="acc-1", name="Основной"),
            ),
            index_info=BaseInfo(id=str(uuid.uuid4()), name="IMOEX"),
            brokers_account_id=str(uuid.uuid4()),
        )
        user_service.list_strategies = AsyncMock(return_value=[item])

        response = client.get("/strategies")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["brokerInfo"]["name"] == "T-Bank"
        assert body[0]["accountDeleted"] is False


class TestRebalancePreview:

    def test_success(self, client, user_service):
        from src.models.rebalance import RebalancePreviewResponse

        preview = RebalancePreviewResponse(
            portfolio=[
                PortfolioPosition(
                    ticker="SBER", name="Сбербанк", uid="uid-1",
                    index_weight=10.0, portfolio_weight=8.0,
                    portfolio_count=100, offer=10,
                )
            ],
            free_cash=1000.0,
            free_cash_after=100.0,
            actions=[RebalanceActionResult(type="BUY", ticker="SBER", quantity=10)],
        )
        user_service.calculate_strategy_rebalance = AsyncMock(return_value=preview)

        strategy_id = uuid.uuid4()
        response = client.get(f"/strategies/{strategy_id}/rebalance")

        assert response.status_code == 200
        body = response.json()
        assert body["freeCash"] == 1000.0
        assert body["actions"][0]["ticker"] == "SBER"
        user_service.calculate_strategy_rebalance.assert_awaited_once()

    def test_not_found(self, client, user_service):
        user_service.calculate_strategy_rebalance = AsyncMock(
            side_effect=UserStrategyNotFoundError("nope")
        )

        response = client.get(f"/strategies/{uuid.uuid4()}/rebalance")

        assert response.status_code == 404

    def test_deleted_account(self, client, user_service):
        user_service.calculate_strategy_rebalance = AsyncMock(
            side_effect=AccountDeletedError("deleted")
        )

        response = client.get(f"/strategies/{uuid.uuid4()}/rebalance")

        assert response.status_code == 409
        assert response.json()["detail"] == "account_deleted"


class TestBondEvents:

    def test_success(self, client, bond_service):
        bond_service.get_bond_events.return_value = [
            SimpleNamespace(
                ticker="RU000A1",
                figi="figi-1",
                short_name="ОФЗ 26240",
                balance=7,
                events=[
                    BondEvent(type=BondEventType.OFFER, date=date(2026, 8, 1)),
                    BondEvent(type=BondEventType.CALL_OPTION, date=date(2026, 9, 15)),
                ],
            ),
        ]

        response = client.get(f"/bonds/events?brokersAccountId={uuid.uuid4()}")

        assert response.status_code == 200
        assert response.json() == [
            {
                "ticker": "RU000A1",
                "name": "ОФЗ 26240",
                "figi": "figi-1",
                "quantity": 7,
                "events": [
                    {"type": "OFFER", "date": "2026-08-01"},
                    {"type": "CALL_OPTION", "date": "2026-09-15"},
                ],
            }
        ]

    def test_empty(self, client, bond_service):
        bond_service.get_bond_events.return_value = []

        response = client.get(f"/bonds/events?brokersAccountId={uuid.uuid4()}")

        assert response.status_code == 200
        assert response.json() == []

    def test_foreign_account(self, client, bond_service):
        bond_service.get_bond_events.side_effect = AccountNotFoundError("x")

        response = client.get(f"/bonds/events?brokersAccountId={uuid.uuid4()}")

        assert response.status_code == 404
        assert response.json()["detail"] == "account_not_found"

    def test_requires_account_id(self, client):
        response = client.get("/bonds/events")

        assert response.status_code == 422


class TestAccounts:
    """Плоский список счетов по всем брокерам — /accounts."""

    @staticmethod
    def _account(has_strategy_id=None):
        return SimpleNamespace(
            id=has_strategy_id or uuid.uuid4(),
            account_id="acc-1",
            account_name="Основной",
            users_broker=SimpleNamespace(
                id=uuid.uuid4(),
                broker_name=BrokerNames.T_BANK,
                sandbox=False,
            ),
        )

    def test_list(self, client, broker_service):
        account = self._account()
        broker_service.list_all_accounts = AsyncMock(return_value=[account])
        broker_service.get_busy_account_ids = AsyncMock(return_value={account.id})

        response = client.get("/accounts")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["accountName"] == "Основной"
        assert body[0]["brokerName"] == BrokerNames.T_BANK.value
        assert body[0]["hasStrategy"] is True

    def test_list_empty(self, client, broker_service):
        broker_service.list_all_accounts = AsyncMock(return_value=[])
        broker_service.get_busy_account_ids = AsyncMock(return_value=set())

        response = client.get("/accounts")

        assert response.status_code == 200
        assert response.json() == []

    def test_refresh(self, client, broker_service):
        account = self._account()
        broker_service.refresh_all_accounts = AsyncMock(return_value=[account])
        broker_service.get_busy_account_ids = AsyncMock(return_value=set())

        response = client.post("/accounts/refresh")

        assert response.status_code == 200
        assert response.json()[0]["hasStrategy"] is False
        broker_service.refresh_all_accounts.assert_awaited_once()

    def test_invalid_broker_token(self, client, broker_service):
        broker_service.list_all_accounts = AsyncMock(side_effect=BrokerAuthError("bad"))

        response = client.get("/accounts")

        assert response.status_code == 422


def make_task(**overrides):
    from src.db.enums import TaskType
    from src.models.scheduler_frequency import ScheduleFrequency
    from datetime import datetime

    fields = dict(
        id=uuid.uuid4(),
        task_type=TaskType.REBALANCE,
        frequency=ScheduleFrequency.WEEKLY,
        params={"strategy_id": str(uuid.uuid4())},
        last_checked_date=datetime(2026, 7, 26, 12, 0, 0),
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


class TestTasks:

    def test_list(self, client, task_service):
        task_service.list_tasks.return_value = [make_task()]

        response = client.get("/tasks")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["type"] == "REBALANCE"
        assert body[0]["frequency"] == "WEEKLY"

    def test_create(self, client, task_service):
        strategy_id = str(uuid.uuid4())
        task_service.create_task.return_value = make_task(
            params={"strategy_id": strategy_id}
        )

        response = client.post("/tasks", json={
            "type": "REBALANCE",
            "frequency": "WEEKLY",
            "params": {"strategy_id": strategy_id},
        })

        assert response.status_code == 201
        assert response.json()["params"] == {"strategy_id": strategy_id}

    def test_create_validation_error(self, client, task_service):
        task_service.create_task.side_effect = TaskValidationError("bad type")

        response = client.post("/tasks", json={
            "type": "NOPE", "frequency": "WEEKLY", "params": {},
        })

        assert response.status_code == 422

    def test_create_duplicate(self, client, task_service):
        task_service.create_task.side_effect = TaskAlreadyExistsError("dup")

        response = client.post("/tasks", json={
            "type": "REBALANCE",
            "frequency": "WEEKLY",
            "params": {"strategy_id": str(uuid.uuid4())},
        })

        assert response.status_code == 409

    def test_update(self, client, task_service, fake_user):
        task_id = uuid.uuid4()
        strategy_id = str(uuid.uuid4())
        task_service.update_task.return_value = make_task(
            params={"strategy_id": strategy_id, "min_free_cash": 7000},
            frequency=ScheduleFrequency.MONTHLY,
        )

        response = client.patch(f"/tasks/{task_id}", json={
            "frequency": "MONTHLY",
            "params": {"min_free_cash": 7000},
        })

        assert response.status_code == 200
        body = response.json()
        assert body["frequency"] == "MONTHLY"
        assert body["params"]["min_free_cash"] == 7000
        task_service.update_task.assert_awaited_once_with(
            fake_user, task_id, "MONTHLY", {"min_free_cash": 7000}
        )

    def test_update_validation_error(self, client, task_service):
        task_service.update_task.side_effect = TaskValidationError("bad threshold")

        response = client.patch(f"/tasks/{uuid.uuid4()}", json={
            "params": {"min_free_cash": -1},
        })

        assert response.status_code == 422

    def test_update_not_found(self, client, task_service):
        task_service.update_task.side_effect = TaskNotFoundError("x")

        response = client.patch(f"/tasks/{uuid.uuid4()}", json={"frequency": "WEEKLY"})

        assert response.status_code == 404

    def test_disable(self, client, task_service, fake_user):
        task_id = uuid.uuid4()
        task_service.disable_task.return_value = None

        response = client.delete(f"/tasks/{task_id}")

        assert response.status_code == 204
        task_service.disable_task.assert_awaited_once_with(fake_user, task_id)

    def test_disable_not_found(self, client, task_service):
        task_service.disable_task.side_effect = TaskNotFoundError("x")

        response = client.delete(f"/tasks/{uuid.uuid4()}")

        assert response.status_code == 404


class TestNotificationChannel:
    """Куда уходят уведомления планировщика (PATCH /users/me/notifications)."""

    @pytest.fixture
    def client(self, client, notification_settings_service):
        from src.api.dependencies.notification_settings import (
            get_notification_settings_service,
        )

        client.app.dependency_overrides[get_notification_settings_service] = (
            lambda: notification_settings_service
        )
        return client

    def test_set_channel(self, client, notification_settings_service, fake_user):
        notification_settings_service.set_channel.return_value = SimpleNamespace(
            email="user@example.com",
            pending_email=None,
            telegram_id=123456789,
            notification_channel=NotificationChannel.ALL,
        )

        response = client.patch("/users/me/notifications", json={"channel": "ALL"})

        assert response.status_code == 200
        body = response.json()
        assert body["notificationChannel"] == "ALL"
        assert body["telegramLinked"] is True
        notification_settings_service.set_channel.assert_awaited_once_with(
            fake_user, NotificationChannel.ALL
        )

    def test_channel_unavailable(self, client, notification_settings_service):
        notification_settings_service.set_channel.side_effect = (
            NotificationChannelUnavailableError("telegram_not_linked")
        )

        response = client.patch("/users/me/notifications", json={"channel": "TELEGRAM"})

        assert response.status_code == 409
        assert response.json()["detail"] == "telegram_not_linked"

    def test_unknown_channel(self, client, notification_settings_service):
        response = client.patch("/users/me/notifications", json={"channel": "SMS"})

        assert response.status_code == 422


class TestChangeEmail:
    """Смена/добавление почты с подтверждением кодом."""

    @pytest.fixture
    def client(self, client, email_change_service):
        from src.api.dependencies.email_change import get_email_change_service

        client.app.dependency_overrides[get_email_change_service] = (
            lambda: email_change_service
        )
        return client

    def test_request(self, client, email_change_service, fake_user):
        email_change_service.request_change.return_value = "new@example.com"

        response = client.post("/users/me/email", json={"email": "New@example.com"})

        assert response.status_code == 200
        assert response.json() == {"pendingEmail": "new@example.com"}
        email_change_service.request_change.assert_awaited_once_with(
            fake_user, "New@example.com", None
        )

    def test_request_with_password(self, client, email_change_service, fake_user):
        email_change_service.request_change.return_value = "new@example.com"

        response = client.post(
            "/users/me/email",
            json={"email": "new@example.com", "password": "secret1"},
        )

        assert response.status_code == 200
        email_change_service.request_change.assert_awaited_once_with(
            fake_user, "new@example.com", "secret1"
        )

    def test_request_password_required(self, client, email_change_service):
        email_change_service.request_change.side_effect = PasswordRequiredError("x")

        response = client.post("/users/me/email", json={"email": "new@example.com"})

        assert response.status_code == 422
        assert response.json()["detail"] == "password_required"

    def test_request_email_taken(self, client, email_change_service):
        email_change_service.request_change.side_effect = EmailAlreadyTakenError("x")

        response = client.post("/users/me/email", json={"email": "taken@example.com"})

        assert response.status_code == 409
        assert response.json()["detail"] == "email_already_registered"

    def test_request_same_email(self, client, email_change_service):
        email_change_service.request_change.side_effect = EmailUnchangedError("x")

        response = client.post("/users/me/email", json={"email": "old@example.com"})

        assert response.status_code == 409
        assert response.json()["detail"] == "email_unchanged"

    def test_request_invalid_email(self, client):
        response = client.post("/users/me/email", json={"email": "not-an-email"})

        assert response.status_code == 422

    def test_request_short_password(self, client):
        response = client.post(
            "/users/me/email", json={"email": "new@example.com", "password": "123"}
        )

        assert response.status_code == 422

    def test_confirm(self, client, email_change_service):
        email_change_service.confirm_change.return_value = "new@example.com"

        response = client.post("/users/me/email/confirm", json={"code": "123456"})

        assert response.status_code == 200
        assert response.json() == {
            "email": "new@example.com",
            "pendingEmail": None,
            "telegramLinked": False,
            "notificationChannel": "EMAIL",
        }

    def test_confirm_invalid_code(self, client, email_change_service):
        email_change_service.confirm_change.side_effect = InvalidCodeError("x")

        response = client.post("/users/me/email/confirm", json={"code": "000000"})

        assert response.status_code == 400
        assert response.json()["detail"] == "invalid_code"

    def test_confirm_expired_code(self, client, email_change_service):
        email_change_service.confirm_change.side_effect = CodeExpiredError("x")

        response = client.post("/users/me/email/confirm", json={"code": "000000"})

        assert response.status_code == 400
        assert response.json()["detail"] == "code_expired"

    def test_confirm_without_request(self, client, email_change_service):
        email_change_service.confirm_change.side_effect = NoPendingEmailError("x")

        response = client.post("/users/me/email/confirm", json={"code": "000000"})

        assert response.status_code == 404
        assert response.json()["detail"] == "no_pending_email"

    def test_resend(self, client, email_change_service):
        email_change_service.resend_code.return_value = "new@example.com"

        response = client.post("/users/me/email/resend")

        assert response.status_code == 200
        assert response.json() == {"pendingEmail": "new@example.com"}

    def test_resend_cooldown(self, client, email_change_service):
        email_change_service.resend_code.side_effect = ResendCooldownError("x")

        response = client.post("/users/me/email/resend")

        assert response.status_code == 429
        assert response.json()["detail"] == "resend_cooldown"

    def test_cancel(self, client, email_change_service):
        email_change_service.cancel_change.return_value = None

        response = client.delete("/users/me/email/pending")

        assert response.status_code == 204

    def test_cancel_without_request(self, client, email_change_service):
        email_change_service.cancel_change.side_effect = NoPendingEmailError("x")

        response = client.delete("/users/me/email/pending")

        assert response.status_code == 404
