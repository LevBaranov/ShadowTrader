"""Лог интеграций бота: те же правила, что и на бэкенде (модуль свой — бот изолирован)."""
import asyncio
import logging

import httpx
import pytest

from bot import logging_setup
from bot.api_client import ShadowTraderApi
from bot.logging_setup import integration_call

TELEGRAM_ID = 123456789


def test_call_is_logged_with_summary(caplog):
    with caplog.at_level(logging.INFO):
        with integration_call("api", "GET /strategies") as call:
            call.add(status=200)

    record = caplog.records[-1]
    assert record.name == "integration.api"
    assert record.message.startswith("GET /strategies | ok | ")
    assert "status=200" in record.message


def test_relative_log_path_is_resolved_from_project_root(monkeypatch):
    monkeypatch.setenv("LOG_PATH", "logs")

    log_dir = logging_setup._log_dir()

    assert log_dir == logging_setup.PROJECT_ROOT / "logs"
    assert "bot" not in log_dir.parts


def api_with_backend(handler):
    client = httpx.AsyncClient(base_url="http://api", transport=httpx.MockTransport(handler))
    return ShadowTraderApi(base_url="http://api", service_key="svc-key", client=client)


def test_backend_calls_are_logged(caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/service/telegram/token":
            return httpx.Response(200, json={"accessToken": "jwt-1", "expiresIn": 900})
        return httpx.Response(200, json=[{"id": "s-1"}])

    api = api_with_backend(handler)

    with caplog.at_level(logging.INFO):
        asyncio.run(api.get_strategies(TELEGRAM_ID))

    messages = [record.message for record in caplog.records if record.name == "integration.api"]
    assert any(message.startswith("POST /service/telegram/token | ok | ") for message in messages)
    assert any(message.startswith("GET /strategies | ok | ") for message in messages)
    # Токен из ответа не должен попадать в лог даже случайно.
    assert not any("jwt-1" in message for message in messages)


def test_error_response_is_logged_as_error(caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/service/telegram/token":
            return httpx.Response(200, json={"accessToken": "jwt-1", "expiresIn": 900})
        return httpx.Response(500, json={"detail": "boom"})

    api = api_with_backend(handler)

    with caplog.at_level(logging.INFO):
        with pytest.raises(Exception):
            asyncio.run(api.get_accounts(TELEGRAM_ID))

    failures = [
        record for record in caplog.records
        if record.name == "integration.api" and record.levelno == logging.ERROR
    ]
    assert failures
    assert "GET /accounts | error | " in failures[-1].message
    assert "status=500 reason=boom" in failures[-1].message
