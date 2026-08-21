"""Тесты смены/добавления почты с подтверждением кодом.

Репозиторий identities и почтовый сервис подменяются in-memory фейками.
"""
import asyncio
import re
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest

from src.core.email_change_service import (
    EmailAlreadyTakenError,
    EmailChangeService,
    EmailUnchangedError,
    NoPendingEmailError,
    PasswordRequiredError,
)
from src.core.verification import (
    MAX_CONFIRM_ATTEMPTS,
    RESEND_COOLDOWN,
    CodeExpiredError,
    InvalidCodeError,
    ResendCooldownError,
    TooManyAttemptsError,
    utcnow,
)
from src.db.enums import AuthProvider


class FakeIdentityRepo:
    def __init__(self):
        self.identities = []
        self.deleted = []

    def _make(self, user_id, provider, external_id, password_hash=None, verified_at=None):
        return SimpleNamespace(
            id=uuid.uuid4(),
            user_id=user_id,
            provider=provider,
            external_id=external_id,
            password_hash=password_hash,
            verified_at=verified_at,
            verification_code_hash=None,
            verification_code_expires_at=None,
            verification_attempts=0,
        )

    def add(self, user_id, provider, external_id, password_hash=None, verified_at=None):
        identity = self._make(user_id, provider, external_id, password_hash, verified_at)
        self.identities.append(identity)
        return identity

    async def get_by_provider_external_id(self, provider, external_id):
        for identity in self.identities:
            if identity.provider == provider and identity.external_id == external_id:
                return identity
        return None

    async def add_identity(self, user_id, provider, external_id, verified_at=None, password_hash=None):
        return self.add(user_id, provider, external_id, password_hash, verified_at)

    async def list_user_identities(self, user_id):
        return [i for i in self.identities if i.user_id == user_id]

    async def delete_identity(self, identity):
        self.identities.remove(identity)
        self.deleted.append(identity)

    async def save(self):
        pass


class FakeEmailService:
    def __init__(self):
        self.sent = []

    async def send(self, to, subject, body):
        self.sent.append((to, subject, body))

    @property
    def last_code(self):
        return re.search(r"\b(\d{6})\b", self.sent[-1][2]).group(1)


@pytest.fixture
def repo():
    return FakeIdentityRepo()


@pytest.fixture
def emails():
    return FakeEmailService()


@pytest.fixture
def service(repo, emails):
    return EmailChangeService(
        identity_repo=repo,
        email_service=emails,
        password_hasher=lambda password: f"hash::{password}",
    )


@pytest.fixture
def user():
    return SimpleNamespace(id=uuid.uuid4())


def with_email(repo, user, email="old@example.com", password_hash="hash::secret"):
    return repo.add(
        user.id, AuthProvider.EMAIL, email, password_hash=password_hash, verified_at=utcnow()
    )


def with_telegram(repo, user, telegram_id="123456789"):
    return repo.add(user.id, AuthProvider.TELEGRAM, telegram_id, verified_at=utcnow())


class TestRequestChange:

    def test_creates_pending_identity_and_sends_code(self, service, repo, emails, user):
        with_email(repo, user)

        result = asyncio.run(service.request_change(user, " New@Example.COM "))

        assert result == "new@example.com"
        assert emails.sent[0][0] == "new@example.com"

        pending = asyncio.run(repo.get_by_provider_external_id(
            AuthProvider.EMAIL, "new@example.com"
        ))
        assert pending is not None
        assert pending.verified_at is None
        assert pending.verification_code_hash

    def test_old_email_still_works_until_confirmed(self, service, repo, user):
        old = with_email(repo, user)

        asyncio.run(service.request_change(user, "new@example.com"))

        assert old in repo.identities
        assert old.verified_at is not None

    def test_carries_password_from_current_identity(self, service, repo, user):
        with_email(repo, user, password_hash="hash::secret")

        asyncio.run(service.request_change(user, "new@example.com"))

        pending = asyncio.run(repo.get_by_provider_external_id(
            AuthProvider.EMAIL, "new@example.com"
        ))
        assert pending.password_hash == "hash::secret"

    def test_same_email_rejected(self, service, repo, user):
        with_email(repo, user, email="old@example.com")

        with pytest.raises(EmailUnchangedError):
            asyncio.run(service.request_change(user, "OLD@example.com"))

    def test_email_of_another_user_rejected(self, service, repo, user):
        with_email(repo, user)
        repo.add(uuid.uuid4(), AuthProvider.EMAIL, "taken@example.com", verified_at=utcnow())

        with pytest.raises(EmailAlreadyTakenError):
            asyncio.run(service.request_change(user, "taken@example.com"))

    def test_repeated_request_reuses_pending_identity(self, service, repo, emails, user):
        with_email(repo, user)

        asyncio.run(service.request_change(user, "first@example.com"))
        asyncio.run(service.request_change(user, "second@example.com"))

        emails_of_user = [
            i for i in repo.identities
            if i.provider == AuthProvider.EMAIL and i.user_id == user.id
        ]
        # Старая подтверждённая + одна ожидающая: первый адрес освобождён.
        assert len(emails_of_user) == 2
        assert {i.external_id for i in emails_of_user} == {"old@example.com", "second@example.com"}
        assert emails.sent[-1][0] == "second@example.com"


class TestAddEmailToTelegramOnlyUser:

    def test_password_required(self, service, repo, user):
        with_telegram(repo, user)

        with pytest.raises(PasswordRequiredError):
            asyncio.run(service.request_change(user, "new@example.com"))

    def test_creates_identity_with_password(self, service, repo, emails, user):
        with_telegram(repo, user)

        asyncio.run(service.request_change(user, "new@example.com", password="secret1"))

        pending = asyncio.run(repo.get_by_provider_external_id(
            AuthProvider.EMAIL, "new@example.com"
        ))
        assert pending.password_hash == "hash::secret1"
        assert pending.verified_at is None

    def test_confirmed_email_becomes_login(self, service, repo, emails, user):
        with_telegram(repo, user)
        asyncio.run(service.request_change(user, "new@example.com", password="secret1"))

        email = asyncio.run(service.confirm_change(user, emails.last_code))

        assert email == "new@example.com"
        identity = asyncio.run(repo.get_by_provider_external_id(
            AuthProvider.EMAIL, "new@example.com"
        ))
        assert identity.verified_at is not None
        # Telegram остаётся вторым способом входа.
        assert len(asyncio.run(repo.list_user_identities(user.id))) == 2


class TestConfirmChange:

    def test_switches_email_and_removes_old(self, service, repo, emails, user):
        old = with_email(repo, user)
        asyncio.run(service.request_change(user, "new@example.com"))

        email = asyncio.run(service.confirm_change(user, emails.last_code))

        assert email == "new@example.com"
        assert old in repo.deleted
        remaining = asyncio.run(repo.list_user_identities(user.id))
        assert [i.external_id for i in remaining] == ["new@example.com"]
        assert remaining[0].verified_at is not None

    def test_wrong_code_counts_attempt(self, service, repo, user):
        with_email(repo, user)
        asyncio.run(service.request_change(user, "new@example.com"))

        with pytest.raises(InvalidCodeError):
            asyncio.run(service.confirm_change(user, "000000"))

        pending = asyncio.run(repo.get_by_provider_external_id(
            AuthProvider.EMAIL, "new@example.com"
        ))
        assert pending.verification_attempts == 1
        assert pending.verified_at is None

    def test_expired_code(self, service, repo, emails, user):
        with_email(repo, user)
        asyncio.run(service.request_change(user, "new@example.com"))

        pending = asyncio.run(repo.get_by_provider_external_id(
            AuthProvider.EMAIL, "new@example.com"
        ))
        pending.verification_code_expires_at = utcnow() - timedelta(seconds=1)

        with pytest.raises(CodeExpiredError):
            asyncio.run(service.confirm_change(user, emails.last_code))

    def test_attempts_limit(self, service, repo, emails, user):
        with_email(repo, user)
        asyncio.run(service.request_change(user, "new@example.com"))

        pending = asyncio.run(repo.get_by_provider_external_id(
            AuthProvider.EMAIL, "new@example.com"
        ))
        pending.verification_attempts = MAX_CONFIRM_ATTEMPTS

        with pytest.raises(TooManyAttemptsError):
            asyncio.run(service.confirm_change(user, emails.last_code))

    def test_without_request(self, service, repo, user):
        with_email(repo, user)

        with pytest.raises(NoPendingEmailError):
            asyncio.run(service.confirm_change(user, "123456"))


class TestResendAndCancel:

    def test_resend_respects_cooldown(self, service, repo, user):
        with_email(repo, user)
        asyncio.run(service.request_change(user, "new@example.com"))

        with pytest.raises(ResendCooldownError):
            asyncio.run(service.resend_code(user))

    def test_resend_after_cooldown(self, service, repo, emails, user):
        with_email(repo, user)
        asyncio.run(service.request_change(user, "new@example.com"))

        pending = asyncio.run(repo.get_by_provider_external_id(
            AuthProvider.EMAIL, "new@example.com"
        ))
        pending.verification_code_expires_at -= RESEND_COOLDOWN + timedelta(seconds=1)
        first_code = emails.last_code

        asyncio.run(service.resend_code(user))

        assert emails.last_code != first_code
        assert emails.sent[-1][0] == "new@example.com"

    def test_cancel_releases_address(self, service, repo, user):
        with_email(repo, user)
        asyncio.run(service.request_change(user, "new@example.com"))

        asyncio.run(service.cancel_change(user))

        assert asyncio.run(repo.get_by_provider_external_id(
            AuthProvider.EMAIL, "new@example.com"
        )) is None
        assert asyncio.run(repo.get_by_provider_external_id(
            AuthProvider.EMAIL, "old@example.com"
        )) is not None

    def test_cancel_keeps_only_email_of_user(self, service, repo, emails, user):
        """У пользователя нет другой почты — адрес не удаляем, только гасим код."""
        with_telegram(repo, user)
        asyncio.run(service.request_change(user, "new@example.com", password="secret1"))

        asyncio.run(service.cancel_change(user))

        pending = asyncio.run(repo.get_by_provider_external_id(
            AuthProvider.EMAIL, "new@example.com"
        ))
        assert pending is not None
        assert pending.verification_code_hash is None

    def test_cancel_without_request(self, service, repo, user):
        with_email(repo, user)

        with pytest.raises(NoPendingEmailError):
            asyncio.run(service.cancel_change(user))
