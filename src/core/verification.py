"""Подтверждение владения почтой одноразовым кодом.

Общая механика для регистрации (RegistrationService) и смены почты
(EmailChangeService): код живёт на самой AuthIdentity — хеш, срок жизни и
счётчик попыток, — поэтому отдельная таблица не нужна.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

CODE_TTL = timedelta(minutes=15)
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_CONFIRM_ATTEMPTS = 5


class InvalidCodeError(Exception):
    """Код не совпал."""


class CodeExpiredError(Exception):
    """Срок действия кода истёк."""


class TooManyAttemptsError(Exception):
    """Превышен лимит попыток ввода кода."""


class ResendCooldownError(Exception):
    """Повторная отправка кода запрошена слишком рано."""


def utcnow() -> datetime:
    # В БД колонки без таймзоны, поэтому храним наивный UTC.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_code(code: str) -> str:
    # Для 6-значного кода с TTL и лимитом попыток достаточно быстрого хеша.
    return hashlib.sha256(code.encode()).hexdigest()


def generate_code() -> str:
    return f"{secrets.randbelow(10 ** 6):06d}"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def can_resend(identity) -> bool:
    """Прошёл ли cooldown с момента отправки последнего кода."""
    if identity.verification_code_expires_at is None:
        return True

    sent_at = identity.verification_code_expires_at - CODE_TTL
    return utcnow() - sent_at >= RESEND_COOLDOWN


async def issue_code(identity, identity_repo, email_service, subject: str, body_template: str) -> None:
    """Выдать новый код на identity и отправить его письмом на identity.external_id.

    body_template — строка с плейсхолдером {code}.
    """
    code = generate_code()

    identity.verification_code_hash = hash_code(code)
    identity.verification_code_expires_at = utcnow() + CODE_TTL
    identity.verification_attempts = 0
    # Сначала фиксируем код в БД: если письмо не уйдёт, пользователь
    # просто запросит повторную отправку.
    await identity_repo.save()

    await email_service.send(
        to=identity.external_id,
        subject=subject,
        body=body_template.format(code=code),
    )


async def verify_code(identity, code: str, identity_repo) -> None:
    """Проверить код на identity. Неудачная попытка увеличивает счётчик."""
    if identity.verification_attempts >= MAX_CONFIRM_ATTEMPTS:
        raise TooManyAttemptsError(identity.external_id)

    if identity.verification_code_expires_at < utcnow():
        raise CodeExpiredError(identity.external_id)

    if not hmac.compare_digest(identity.verification_code_hash, hash_code(code)):
        identity.verification_attempts += 1
        await identity_repo.save()
        raise InvalidCodeError(identity.external_id)


async def mark_verified(identity, identity_repo) -> None:
    """Пометить identity подтверждённой и погасить код."""
    identity.verified_at = utcnow()
    identity.verification_code_hash = None
    identity.verification_code_expires_at = None
    identity.verification_attempts = 0
    await identity_repo.save()
