"""Тесты выбора канала уведомлений."""
import asyncio
import uuid
from types import SimpleNamespace

import httpx
import pytest

from src.models.notification_channel import NotificationChannel
from src.services.notifications import NotificationService, TelegramChannel


class FakeTelegram:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    async def send(self, chat_id, text):
        if self.fail:
            raise httpx.ConnectError("boom")
        self.sent.append((chat_id, text))


class FakeEmail:
    def __init__(self):
        self.sent = []

    async def send(self, to, subject, body):
        self.sent.append((to, subject, body))


def make_user(telegram_id=None, email=None, channel=NotificationChannel.TELEGRAM):
    return SimpleNamespace(
        id=uuid.uuid4(),
        telegram_id=telegram_id,
        email=email,
        notification_channel=channel,
    )


def test_uses_telegram_when_chosen():
    telegram, email = FakeTelegram(), FakeEmail()
    service = NotificationService(telegram=telegram, email=email)

    asyncio.run(service.notify(make_user(telegram_id=123456789, email="u@e.com"), "Тема", "Текст"))

    assert telegram.sent == [(123456789, "Текст")]
    assert email.sent == []


def test_uses_email_when_chosen():
    """Telegram привязан, но пользователь выбрал почту — Telegram не трогаем."""
    telegram, email = FakeTelegram(), FakeEmail()
    service = NotificationService(telegram=telegram, email=email)

    user = make_user(
        telegram_id=123456789, email="u@e.com", channel=NotificationChannel.EMAIL
    )
    asyncio.run(service.notify(user, "Тема", "Текст"))

    assert telegram.sent == []
    assert email.sent == [("u@e.com", "Тема", "Текст")]


def test_all_sends_to_both_channels():
    telegram, email = FakeTelegram(), FakeEmail()
    service = NotificationService(telegram=telegram, email=email)

    user = make_user(
        telegram_id=123456789, email="u@e.com", channel=NotificationChannel.ALL
    )
    asyncio.run(service.notify(user, "Тема", "Текст"))

    assert telegram.sent == [(123456789, "Текст")]
    assert email.sent == [("u@e.com", "Тема", "Текст")]


def test_all_skips_unavailable_channel():
    telegram, email = FakeTelegram(), FakeEmail()
    service = NotificationService(telegram=telegram, email=email)

    user = make_user(email="u@e.com", channel=NotificationChannel.ALL)
    asyncio.run(service.notify(user, "Тема", "Текст"))

    assert telegram.sent == []
    assert email.sent == [("u@e.com", "Тема", "Текст")]


def test_falls_back_when_chosen_channel_unavailable():
    """Telegram выбран, но не привязан — уведомление всё равно доходит на почту."""
    telegram, email = FakeTelegram(), FakeEmail()
    service = NotificationService(telegram=telegram, email=email)

    asyncio.run(service.notify(make_user(email="u@e.com"), "Тема", "Текст"))

    assert telegram.sent == []
    assert email.sent == [("u@e.com", "Тема", "Текст")]


def test_no_channels_available_is_silent():
    telegram, email = FakeTelegram(), FakeEmail()
    service = NotificationService(telegram=telegram, email=email)

    asyncio.run(service.notify(make_user(), "Тема", "Текст"))

    assert telegram.sent == []
    assert email.sent == []


def test_send_failure_does_not_raise():
    service = NotificationService(telegram=FakeTelegram(fail=True), email=FakeEmail())

    asyncio.run(service.notify(make_user(telegram_id=1), "Тема", "Текст"))


def test_failure_in_one_channel_does_not_block_other():
    telegram, email = FakeTelegram(fail=True), FakeEmail()
    service = NotificationService(telegram=telegram, email=email)

    user = make_user(telegram_id=1, email="u@e.com", channel=NotificationChannel.ALL)
    asyncio.run(service.notify(user, "Тема", "Текст"))

    assert email.sent == [("u@e.com", "Тема", "Текст")]


def test_telegram_channel_sends_via_bot_api():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    client = httpx.AsyncClient(
        base_url="https://api.telegram.org", transport=httpx.MockTransport(handler)
    )
    channel = TelegramChannel(bot_token="123:abc", client=client)

    asyncio.run(channel.send(123456789, "Привет"))

    assert requests[0].url.path == "/bot123:abc/sendMessage"
