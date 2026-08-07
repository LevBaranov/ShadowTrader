"""Тесты единого лога интеграций: формат строки, маскирование, подробный режим."""
import logging
from pathlib import Path

import pytest

from src import logging_setup
from src.logging_setup import integration_call, integration_logger


def last_message(caplog) -> str:
    return caplog.records[-1].message


def test_success_writes_one_line_with_summary(caplog):
    with caplog.at_level(logging.INFO):
        with integration_call("broker", "get_positions", account="acc-1") as call:
            call.add(shares=3, bonds=1)

    record = caplog.records[-1]
    assert record.name == "integration.broker"
    assert record.levelno == logging.INFO
    assert record.message.startswith("get_positions | ok | ")
    assert "account=acc-1 shares=3 bonds=1" in record.message


def test_error_is_logged_and_reraised(caplog):
    with caplog.at_level(logging.INFO):
        with pytest.raises(ValueError):
            with integration_call("moex", "get_bonds", url="https://iss.moex.com"):
                raise ValueError("boom")

    record = caplog.records[-1]
    assert record.levelno == logging.ERROR
    assert "get_bonds | error | " in record.message
    assert "error=ValueError: boom" in record.message


def test_skipped_call_has_reason(caplog):
    with caplog.at_level(logging.INFO):
        with integration_call("telegram", "send_message", chat_id=1) as call:
            call.skipped("bot_token_not_configured")

    assert "send_message | skipped | " in last_message(caplog)
    assert "reason=bot_token_not_configured" in last_message(caplog)


def test_secrets_are_masked(caplog):
    with caplog.at_level(logging.INFO):
        with integration_call("broker", "auth", token="t.super-secret", password="qwerty"):
            pass

    assert "t.super-secret" not in last_message(caplog)
    assert "token=***" in last_message(caplog)
    assert "password=***" in last_message(caplog)


def test_secrets_inside_bodies_are_masked(caplog, monkeypatch):
    monkeypatch.setattr(logging_setup, "VERBOSE", True)

    with caplog.at_level(logging.DEBUG):
        with integration_call("api", "POST /token") as call:
            call.detail(response='{"accessToken":"jwt-value","expiresIn":900}')

    assert "jwt-value" not in caplog.records[-1].message
    assert '"accessToken":"***"' in caplog.records[-1].message
    assert '"expiresIn":900' in caplog.records[-1].message


def test_unsuccessful_response_is_logged_as_error(caplog):
    with caplog.at_level(logging.INFO):
        with integration_call("api", "GET /accounts") as call:
            call.add(status=500)
            call.failed("boom")

    record = caplog.records[-1]
    assert record.levelno == logging.ERROR
    assert "GET /accounts | error | " in record.message
    assert "status=500 reason=boom" in record.message


def test_empty_values_are_skipped(caplog):
    with caplog.at_level(logging.INFO):
        with integration_call("email", "send", to="u@e.com", subject=None):
            pass

    assert "subject" not in last_message(caplog)
    assert "to=u@e.com" in last_message(caplog)


def test_long_values_are_trimmed(caplog):
    with caplog.at_level(logging.INFO):
        with integration_call("moex", "get_bonds") as call:
            call.add(tickers=["SBER"] * 500)

    assert len(last_message(caplog)) < 300
    assert "…(" in last_message(caplog)


def test_details_are_written_only_in_verbose_mode(caplog, monkeypatch):
    with caplog.at_level(logging.DEBUG):
        with integration_call("email", "send", to="u@e.com") as call:
            call.detail(body="Код подтверждения: 123456")

    assert len(caplog.records) == 1

    caplog.clear()
    monkeypatch.setattr(logging_setup, "VERBOSE", True)

    with caplog.at_level(logging.DEBUG):
        with integration_call("email", "send", to="u@e.com") as call:
            call.detail(body="Код подтверждения: 123456")

    assert len(caplog.records) == 2
    assert caplog.records[-1].levelno == logging.DEBUG
    assert "send | detail | body=Код подтверждения: 123456" == caplog.records[-1].message


def test_relative_log_path_is_resolved_from_project_root(monkeypatch):
    """Логи не должны появляться там, откуда запущен процесс (и внутри пакетов с кодом)."""
    monkeypatch.setenv("LOG_PATH", "logs")

    log_dir = logging_setup._log_dir()

    assert log_dir == logging_setup.PROJECT_ROOT / "logs"
    assert "src" not in log_dir.parts


def test_absolute_log_path_is_used_as_is(monkeypatch):
    monkeypatch.setenv("LOG_PATH", "/var/log/shadowtrader")

    assert logging_setup._log_dir() == Path("/var/log/shadowtrader")


def test_no_files_are_created_when_disabled():
    """LOG_ENABLED=0 (выставлен в conftest) — файловых хендлеров нет."""
    assert logging_setup.ENABLED is False
    assert integration_logger("broker").handlers == []
