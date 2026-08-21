"""Регистрация пользователя с подтверждением почты кодом из письма.

Флоу: register (создаёт пользователя с неподтверждённой EMAIL-identity и шлёт код) →
confirm (проверяет код и помечает identity подтверждённой). До подтверждения
логин запрещён — это отсекает регистрации на чужие/несуществующие адреса.

Механика одноразового кода общая со сменой почты — см. src/core/verification.py.
"""
from src.core.verification import (
    CODE_TTL,
    MAX_CONFIRM_ATTEMPTS,
    RESEND_COOLDOWN,
    CodeExpiredError,
    InvalidCodeError,
    ResendCooldownError,
    TooManyAttemptsError,
    can_resend,
    hash_code as _hash_code,
    issue_code,
    mark_verified,
    normalize_email,
    utcnow as _utcnow,
    verify_code,
)
from src.db.enums import AuthProvider
from src.db.models.auth_identity import AuthIdentity

CONFIRMATION_EMAIL_SUBJECT = "Код подтверждения — ShadowTrader"
CONFIRMATION_EMAIL_BODY = (
    "Ваш код подтверждения: {code}\n\n"
    "Код действует 15 минут.\n"
    "Если вы не регистрировались в ShadowTrader, просто проигнорируйте это письмо."
)


class EmailAlreadyRegisteredError(Exception):
    """Почта уже зарегистрирована и подтверждена."""


class RegistrationNotFoundError(Exception):
    """Нет незавершённой регистрации для этой почты."""


class RegistrationService:

    def __init__(self, identity_repo, email_service, password_hasher):
        self.identity_repo = identity_repo
        self.email_service = email_service
        self.password_hasher = password_hasher

    async def register(self, email: str, password: str) -> None:
        email = normalize_email(email)
        identity = await self.identity_repo.get_by_provider_external_id(
            AuthProvider.EMAIL, email
        )

        if identity and identity.verified_at is not None:
            raise EmailAlreadyRegisteredError(email)

        password_hash = self.password_hasher(password)

        if identity is None:
            identity = await self.identity_repo.create_user_with_identity(
                AuthProvider.EMAIL, email, password_hash=password_hash
            )
        else:
            # Повторная регистрация до подтверждения: обновляем пароль и шлём новый код.
            identity.password_hash = password_hash

        await self._issue_code(identity)

    async def confirm(self, email: str, code: str) -> AuthIdentity:
        identity = await self._get_pending_identity(email)

        if not identity.verification_code_hash or not identity.verification_code_expires_at:
            raise RegistrationNotFoundError(email)

        await verify_code(identity, code, self.identity_repo)
        await mark_verified(identity, self.identity_repo)

        return identity

    async def resend_code(self, email: str) -> None:
        identity = await self._get_pending_identity(email)

        if not can_resend(identity):
            raise ResendCooldownError(email)

        await self._issue_code(identity)

    async def _get_pending_identity(self, email: str) -> AuthIdentity:
        identity = await self.identity_repo.get_by_provider_external_id(
            AuthProvider.EMAIL, normalize_email(email)
        )

        if identity is None or identity.verified_at is not None:
            raise RegistrationNotFoundError(email)

        return identity

    async def _issue_code(self, identity: AuthIdentity) -> None:
        await issue_code(
            identity,
            self.identity_repo,
            self.email_service,
            CONFIRMATION_EMAIL_SUBJECT,
            CONFIRMATION_EMAIL_BODY,
        )
