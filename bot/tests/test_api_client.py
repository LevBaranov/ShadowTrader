"""Тесты HTTP-клиента бота: кэш токена, рефреш на 401, маппинг ошибок.

Сеть подменяется httpx.MockTransport — реальный бэкенд не нужен.
"""
import asyncio
import json

import httpx
import pytest

from bot.api_client import ShadowTraderApi, ApiError, TelegramNotLinkedError

TELEGRAM_ID = 123456789
SERVICE_KEY = "test-key"


class FakeBackend:
    """Программируемый бэкенд: считает обмены токена и отдаёт заготовленные ответы."""

    def __init__(self):
        self.token_exchanges = 0
        self.requests = []
        self.linked = True
        self.expires_in = 900
        # Однократно ответить 401 на следующий доменный запрос.
        self.next_domain_401 = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)

        if request.url.path == "/service/telegram/token":
            assert request.headers["X-Service-Key"] == SERVICE_KEY
            if not self.linked:
                return httpx.Response(404, json={"detail": "telegram_not_linked"})
            self.token_exchanges += 1
            return httpx.Response(200, json={
                "accessToken": f"token-{self.token_exchanges}",
                "tokenType": "bearer",
                "expiresIn": self.expires_in,
            })

        if request.url.path == "/service/telegram/register":
            return httpx.Response(201, json={"userId": "u-1"})

        if self.next_domain_401:
            self.next_domain_401 = False
            return httpx.Response(401, json={"detail": "Invalid token"})

        if request.url.path == "/strategies":
            return httpx.Response(200, json=[{"id": "s-1"}])

        if request.url.path.startswith("/tasks/") and request.method == "DELETE":
            return httpx.Response(204)

        if request.url.path.startswith("/brokers/") and request.method == "PATCH":
            body = json.loads(request.content)
            return httpx.Response(200, json={
                "id": request.url.path.rsplit("/", 1)[-1],
                "brokerName": "T-Bank",
                "sandbox": False,
                "commission": body["commission"],
            })

        return httpx.Response(404, json={"detail": "not_found"})


@pytest.fixture
def backend():
    return FakeBackend()


@pytest.fixture
def api(backend):
    client = httpx.AsyncClient(
        base_url="http://test", transport=httpx.MockTransport(backend.handler)
    )
    return ShadowTraderApi(base_url="http://test", service_key=SERVICE_KEY, client=client)


def test_token_cached_between_requests(api, backend):
    asyncio.run(api.get_strategies(TELEGRAM_ID))
    asyncio.run(api.get_strategies(TELEGRAM_ID))

    assert backend.token_exchanges == 1


def test_expired_token_is_refreshed(api, backend):
    backend.expires_in = 1  # меньше запаса в 30 сек — токен сразу «протухший»

    asyncio.run(api.get_strategies(TELEGRAM_ID))
    asyncio.run(api.get_strategies(TELEGRAM_ID))

    assert backend.token_exchanges == 2


def test_retry_once_on_401(api, backend):
    asyncio.run(api.get_strategies(TELEGRAM_ID))
    backend.next_domain_401 = True

    result = asyncio.run(api.get_strategies(TELEGRAM_ID))

    assert result == [{"id": "s-1"}]
    assert backend.token_exchanges == 2
    # Повторный запрос ушёл со свежим токеном.
    auth_headers = [r.headers.get("Authorization") for r in backend.requests
                    if r.url.path == "/strategies"]
    assert auth_headers[-1] == "Bearer token-2"


def test_not_linked_raises(api, backend):
    backend.linked = False

    with pytest.raises(TelegramNotLinkedError):
        asyncio.run(api.get_strategies(TELEGRAM_ID))

    assert asyncio.run(api.is_linked(TELEGRAM_ID)) is False


def test_is_linked_true(api, backend):
    assert asyncio.run(api.is_linked(TELEGRAM_ID)) is True


def test_api_error_carries_detail(api, backend):
    with pytest.raises(ApiError) as exc_info:
        asyncio.run(api._request("GET", "/nope", TELEGRAM_ID))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "not_found"


def test_delete_returns_none_on_204(api, backend):
    assert asyncio.run(api.delete_task(TELEGRAM_ID, "t-1")) is None


def test_register_uses_service_key(api, backend):
    result = asyncio.run(api.register_telegram_user(TELEGRAM_ID))

    assert result == {"userId": "u-1"}
    register_request = [r for r in backend.requests
                        if r.url.path == "/service/telegram/register"][0]
    assert register_request.headers["X-Service-Key"] == SERVICE_KEY
    assert json.loads(register_request.content) == {"telegramId": TELEGRAM_ID}


def test_update_broker_sends_commission_as_fraction(api, backend):
    """Комиссия уходит долей строкой — Decimal в JSON не сериализуется."""
    from decimal import Decimal

    result = asyncio.run(api.update_broker(TELEGRAM_ID, "broker-1", Decimal("0.003")))

    assert result["commission"] == "0.003"
    patch_request = [r for r in backend.requests
                     if r.method == "PATCH" and r.url.path == "/brokers/broker-1"][0]
    assert json.loads(patch_request.content) == {"commission": "0.003"}
