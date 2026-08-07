"""Тесты привязки Telegram и регистрации через Telegram (fake-репозитории)."""
import asyncio
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest

from src.db.enums import AuthProvider
from src.core.verification import hash_code, utcnow
from src.core.telegram_link_service import (
    TelegramLinkService,
    TelegramNotLinkedError,
    TelegramAlreadyLinkedError,
    LinkCodeInvalidError,
    LastLoginMethodError,
    LINK_CODE_TTL,
)


class FakeIdentityRepo:
    def __init__(self):
        self.identities = []

    async def get_by_provider_external_id(self, provider, external_id):
        for identity in self.identities:
            if identity.provider == provider and identity.external_id == external_id:
                return identity
        return None

    async def create_user_with_identity(self, provider, external_id, password_hash=None, verified_at=None):
        identity = SimpleNamespace(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            provider=provider,
            external_id=external_id,
            password_hash=password_hash,
            verified_at=verified_at,
        )
        self.identities.append(identity)
        return identity

    async def add_identity(self, user_id, provider, external_id, verified_at=None):
        identity = SimpleNamespace(
            id=uuid.uuid4(),
            user_id=user_id,
            provider=provider,
            external_id=external_id,
            password_hash=None,
            verified_at=verified_at,
        )
        self.identities.append(identity)
        return identity

    async def list_user_identities(self, user_id):
        return [i for i in self.identities if i.user_id == user_id]

    async def delete_identity(self, identity):
        self.identities.remove(identity)

    async def save(self):
        pass


class FakeLinkRepo:
    def __init__(self):
        self.requests = []

    async def get_by_telegram_id(self, telegram_id):
        for request in self.requests:
            if request.telegram_id == telegram_id:
                return request
        return None

    async def get_by_code_hash(self, code_hash):
        for request in self.requests:
            if request.code_hash == code_hash:
                return request
        return None

    async def create(self, telegram_id, code_hash, expires_at):
        request = SimpleNamespace(
            telegram_id=telegram_id, code_hash=code_hash, expires_at=expires_at
        )
        self.requests.append(request)
        return request

    async def delete(self, request):
        self.requests.remove(request)

    async def save(self):
        pass


TELEGRAM_ID = 123456789


@pytest.fixture
def identity_repo():
    return FakeIdentityRepo()


@pytest.fixture
def link_repo():
    return FakeLinkRepo()


@pytest.fixture
def service(identity_repo, link_repo):
    return TelegramLinkService(identity_repo=identity_repo, link_repo=link_repo)


def make_user(identity_repo, providers=(AuthProvider.EMAIL,)):
    user_id = uuid.uuid4()
    for provider in providers:
        identity_repo.identities.append(SimpleNamespace(
            id=uuid.uuid4(),
            user_id=user_id,
            provider=provider,
            external_id="user@example.com" if provider == AuthProvider.EMAIL else str(TELEGRAM_ID),
            password_hash=None,
            verified_at=utcnow(),
        ))
    return SimpleNamespace(id=user_id)


class TestTokenExchange:

    def test_linked_user(self, service, identity_repo):
        identity = asyncio.run(identity_repo.create_user_with_identity(
            AuthProvider.TELEGRAM, str(TELEGRAM_ID), verified_at=utcnow()
        ))

        user_id = asyncio.run(service.get_linked_user_id(TELEGRAM_ID))

        assert user_id == identity.user_id

    def test_not_linked(self, service):
        with pytest.raises(TelegramNotLinkedError):
            asyncio.run(service.get_linked_user_id(TELEGRAM_ID))


class TestTelegramRegistration:

    def test_creates_user_with_verified_identity(self, service, identity_repo):
        identity = asyncio.run(service.register_telegram_user(TELEGRAM_ID))

        assert identity.provider == AuthProvider.TELEGRAM
        assert identity.external_id == str(TELEGRAM_ID)
        assert identity.verified_at is not None

    def test_already_linked(self, service):
        asyncio.run(service.register_telegram_user(TELEGRAM_ID))

        with pytest.raises(TelegramAlreadyLinkedError):
            asyncio.run(service.register_telegram_user(TELEGRAM_ID))


class TestLinkRequests:

    def test_create_and_confirm(self, service, identity_repo, link_repo):
        user = make_user(identity_repo)

        code, expires_at = asyncio.run(service.create_link_request(TELEGRAM_ID))
        assert len(code) == 6
        # В хранилище — только хеш кода.
        assert link_repo.requests[0].code_hash == hash_code(code)

        telegram_id = asyncio.run(service.confirm_link(user, code))

        assert telegram_id == TELEGRAM_ID
        assert asyncio.run(service.get_linked_user_id(TELEGRAM_ID)) == user.id
        assert link_repo.requests == []

    def test_reissue_invalidates_old_code(self, service, identity_repo, link_repo):
        user = make_user(identity_repo)

        old_code, _ = asyncio.run(service.create_link_request(TELEGRAM_ID))
        new_code, _ = asyncio.run(service.create_link_request(TELEGRAM_ID))

        assert len(link_repo.requests) == 1
        with pytest.raises(LinkCodeInvalidError):
            asyncio.run(service.confirm_link(user, old_code))
        asyncio.run(service.confirm_link(user, new_code))

    def test_expired_code(self, service, identity_repo, link_repo):
        user = make_user(identity_repo)

        code, _ = asyncio.run(service.create_link_request(TELEGRAM_ID))
        link_repo.requests[0].expires_at = utcnow() - timedelta(minutes=1)

        with pytest.raises(LinkCodeInvalidError):
            asyncio.run(service.confirm_link(user, code))

    def test_unknown_code(self, service, identity_repo):
        user = make_user(identity_repo)

        with pytest.raises(LinkCodeInvalidError):
            asyncio.run(service.confirm_link(user, "WRONG1"))

    def test_request_for_already_linked_telegram(self, service):
        asyncio.run(service.register_telegram_user(TELEGRAM_ID))

        with pytest.raises(TelegramAlreadyLinkedError):
            asyncio.run(service.create_link_request(TELEGRAM_ID))

    def test_confirm_when_user_already_has_telegram(self, service, identity_repo):
        user = make_user(identity_repo, providers=(AuthProvider.EMAIL, AuthProvider.TELEGRAM))

        code, _ = asyncio.run(service.create_link_request(999000111))

        with pytest.raises(TelegramAlreadyLinkedError):
            asyncio.run(service.confirm_link(user, code))

    def test_code_normalization(self, service, identity_repo):
        """Код из письма может прийти в нижнем регистре и с пробелами."""
        user = make_user(identity_repo)

        code, _ = asyncio.run(service.create_link_request(TELEGRAM_ID))

        telegram_id = asyncio.run(service.confirm_link(user, f"  {code.lower()} "))
        assert telegram_id == TELEGRAM_ID


class TestUnlink:

    def test_unlink_removes_identity(self, service, identity_repo):
        user = make_user(identity_repo, providers=(AuthProvider.EMAIL, AuthProvider.TELEGRAM))

        asyncio.run(service.unlink(user))

        with pytest.raises(TelegramNotLinkedError):
            asyncio.run(service.get_linked_user_id(TELEGRAM_ID))

    def test_unlink_not_linked(self, service, identity_repo):
        user = make_user(identity_repo)

        with pytest.raises(TelegramNotLinkedError):
            asyncio.run(service.unlink(user))

    def test_unlink_last_login_method(self, service, identity_repo):
        user = make_user(identity_repo, providers=(AuthProvider.TELEGRAM,))

        with pytest.raises(LastLoginMethodError):
            asyncio.run(service.unlink(user))
