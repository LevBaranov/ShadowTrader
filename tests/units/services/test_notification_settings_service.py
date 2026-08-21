"""Тесты настройки канала уведомлений."""
import asyncio
import uuid
from types import SimpleNamespace

import pytest

from src.core.notification_settings_service import (
    NotificationChannelUnavailableError,
    NotificationSettingsService,
)
from src.models.notification_channel import NotificationChannel


class FakeUserRepo:
    def __init__(self):
        self.saved = 0

    async def save(self):
        self.saved += 1


def make_user(telegram_id=None, email=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        telegram_id=telegram_id,
        email=email,
        notification_channel=NotificationChannel.TELEGRAM,
    )


@pytest.fixture
def repo():
    return FakeUserRepo()


@pytest.fixture
def service(repo):
    return NotificationSettingsService(user_repo=repo)


def test_sets_email_channel(service, repo):
    user = make_user(telegram_id=1, email="u@e.com")

    asyncio.run(service.set_channel(user, NotificationChannel.EMAIL))

    assert user.notification_channel == NotificationChannel.EMAIL
    assert repo.saved == 1


def test_sets_all_with_one_channel_available(service):
    """ALL допустим и с одним каналом — второй заработает после привязки."""
    user = make_user(email="u@e.com")

    asyncio.run(service.set_channel(user, NotificationChannel.ALL))

    assert user.notification_channel == NotificationChannel.ALL


def test_telegram_without_link_rejected(service, repo):
    user = make_user(email="u@e.com")

    with pytest.raises(NotificationChannelUnavailableError):
        asyncio.run(service.set_channel(user, NotificationChannel.TELEGRAM))

    assert user.notification_channel == NotificationChannel.TELEGRAM
    assert repo.saved == 0


def test_email_without_confirmed_address_rejected(service):
    user = make_user(telegram_id=1)

    with pytest.raises(NotificationChannelUnavailableError):
        asyncio.run(service.set_channel(user, NotificationChannel.EMAIL))


def test_all_without_any_channel_rejected(service):
    with pytest.raises(NotificationChannelUnavailableError):
        asyncio.run(service.set_channel(make_user(), NotificationChannel.ALL))
