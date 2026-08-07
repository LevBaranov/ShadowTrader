"""Тесты логики регистрации с подтверждением почты.

Репозиторий identities и почтовый сервис подменяются in-memory фейками —
проверяем сценарии выдачи/проверки кода без БД и SMTP.
"""
import asyncio
import re
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest

from src.db.enums import AuthProvider
from src.core.registration_service import (
    RegistrationService,
    EmailAlreadyRegisteredError,
    RegistrationNotFoundError,
    InvalidCodeError,
    CodeExpiredError,
    TooManyAttemptsError,
    ResendCooldownError,
    RESEND_COOLDOWN,
    MAX_CONFIRM_ATTEMPTS,
    _utcnow,
)


class FakeIdentityRepo:
    def __init__(self):
        self.identities = {}

    async def get_by_provider_external_id(self, provider, external_id):
        return self.identities.get((provider, external_id))

    async def create_user_with_identity(self, provider, external_id, password_hash=None, verified_at=None):
        identity = SimpleNamespace(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            provider=provider,
            external_id=external_id,
            password_hash=password_hash,
            verified_at=verified_at,
            verification_code_hash=None,
            verification_code_expires_at=None,
            verification_attempts=0,
        )
        self.identities[(provider, external_id)] = identity
        return identity

    async def save(self):
        pass

    def email_identity(self, email):
        return self.identities[(AuthProvider.EMAIL, email)]


class FakeEmailService:
    def __init__(self):
        self.sent = []

    async def send(self, to, subject, body):
        self.sent.append((to, subject, body))

    def last_code(self):
        return re.search(r"\d{6}", self.sent[-1][2]).group()


@pytest.fixture
def repo():
    return FakeIdentityRepo()


@pytest.fixture
def email_service():
    return FakeEmailService()


@pytest.fixture
def service(repo, email_service):
    return RegistrationService(
        identity_repo=repo,
        email_service=email_service,
        password_hasher=lambda password: f"hashed:{password}",
    )


def test_register_creates_unverified_identity_and_sends_code(service, repo, email_service):
    asyncio.run(service.register("User@Example.com ", "secret123"))

    identity = repo.email_identity("user@example.com")
    assert identity.verified_at is None
    assert identity.password_hash == "hashed:secret123"
    assert identity.verification_code_hash is not None

    assert len(email_service.sent) == 1
    assert email_service.sent[0][0] == "user@example.com"
    assert email_service.last_code() in email_service.sent[0][2]


def test_register_verified_email_raises(service, repo):
    asyncio.run(service.register("user@example.com", "secret123"))
    repo.email_identity("user@example.com").verified_at = _utcnow()

    with pytest.raises(EmailAlreadyRegisteredError):
        asyncio.run(service.register("user@example.com", "another123"))


def test_register_again_before_confirm_updates_password_and_resends(service, repo, email_service):
    asyncio.run(service.register("user@example.com", "secret123"))
    asyncio.run(service.register("user@example.com", "newpass123"))

    identity = repo.email_identity("user@example.com")
    assert identity.password_hash == "hashed:newpass123"
    assert len(email_service.sent) == 2


def test_confirm_with_valid_code_verifies_identity(service, repo, email_service):
    asyncio.run(service.register("user@example.com", "secret123"))

    identity = asyncio.run(service.confirm("user@example.com", email_service.last_code()))

    assert identity.verified_at is not None
    assert identity.verification_code_hash is None
    assert identity.verification_code_expires_at is None
    assert identity.user_id is not None


def test_confirm_with_wrong_code_increments_attempts(service, repo, email_service):
    asyncio.run(service.register("user@example.com", "secret123"))
    wrong_code = "000000" if email_service.last_code() != "000000" else "111111"

    with pytest.raises(InvalidCodeError):
        asyncio.run(service.confirm("user@example.com", wrong_code))

    assert repo.email_identity("user@example.com").verification_attempts == 1


def test_confirm_after_max_attempts_raises(service, repo, email_service):
    asyncio.run(service.register("user@example.com", "secret123"))
    repo.email_identity("user@example.com").verification_attempts = MAX_CONFIRM_ATTEMPTS

    with pytest.raises(TooManyAttemptsError):
        asyncio.run(service.confirm("user@example.com", email_service.last_code()))


def test_confirm_expired_code_raises(service, repo, email_service):
    asyncio.run(service.register("user@example.com", "secret123"))
    repo.email_identity("user@example.com").verification_code_expires_at = _utcnow() - timedelta(minutes=1)

    with pytest.raises(CodeExpiredError):
        asyncio.run(service.confirm("user@example.com", email_service.last_code()))


def test_confirm_unknown_email_raises(service):
    with pytest.raises(RegistrationNotFoundError):
        asyncio.run(service.confirm("nobody@example.com", "123456"))


def test_resend_within_cooldown_raises(service, email_service):
    asyncio.run(service.register("user@example.com", "secret123"))

    with pytest.raises(ResendCooldownError):
        asyncio.run(service.resend_code("user@example.com"))


def test_resend_after_cooldown_sends_new_code(service, repo, email_service):
    asyncio.run(service.register("user@example.com", "secret123"))
    identity = repo.email_identity("user@example.com")
    identity.verification_code_expires_at -= RESEND_COOLDOWN

    asyncio.run(service.resend_code("user@example.com"))

    assert len(email_service.sent) == 2


def test_resend_for_verified_identity_raises(service, repo):
    asyncio.run(service.register("user@example.com", "secret123"))
    repo.email_identity("user@example.com").verified_at = _utcnow()

    with pytest.raises(RegistrationNotFoundError):
        asyncio.run(service.resend_code("user@example.com"))
