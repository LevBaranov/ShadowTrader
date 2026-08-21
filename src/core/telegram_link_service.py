"""Привязка Telegram к учётке и регистрация через Telegram.

Два сценария входа из бота:
- register_telegram_user — новый пользователь, у которого нет веб-аккаунта:
  создаём User + TELEGRAM-identity (владение чатом подтверждено самим диалогом);
- create_link_request/confirm_link — привязка к существующей учётке: бот выдаёт
  одноразовый код, пользователь подтверждает его на фронте под своим JWT.
"""
import hmac
import secrets
import uuid
from datetime import datetime, timedelta

from src.core.verification import hash_code, utcnow
from src.db.enums import AuthProvider
from src.db.models.auth_identity import AuthIdentity

LINK_CODE_TTL = timedelta(minutes=10)
# Без похожих символов (0/O, 1/I), чтобы код легко перепечатывался.
LINK_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LINK_CODE_LENGTH = 6


class TelegramNotLinkedError(Exception):
    """Telegram-аккаунт не привязан ни к одной учётке."""


class TelegramAlreadyLinkedError(Exception):
    """Telegram-аккаунт уже привязан (или у учётки уже есть Telegram)."""


class LinkCodeInvalidError(Exception):
    """Код привязки не найден или истёк."""


class LastLoginMethodError(Exception):
    """Нельзя удалить единственный способ входа."""


def _generate_code() -> str:
    return "".join(secrets.choice(LINK_CODE_ALPHABET) for _ in range(LINK_CODE_LENGTH))


class TelegramLinkService:

    def __init__(self, identity_repo, link_repo):
        self.identity_repo = identity_repo
        self.link_repo = link_repo

    async def get_linked_user_id(self, telegram_id: int) -> uuid.UUID:
        """Пользователь, к которому привязан telegram_id (для обмена на JWT)."""
        identity = await self._get_telegram_identity(telegram_id)

        if identity is None:
            raise TelegramNotLinkedError(telegram_id)

        return identity.user_id

    async def register_telegram_user(self, telegram_id: int) -> AuthIdentity:
        """Регистрация нового пользователя прямо из Telegram."""
        if await self._get_telegram_identity(telegram_id) is not None:
            raise TelegramAlreadyLinkedError(telegram_id)

        return await self.identity_repo.create_user_with_identity(
            AuthProvider.TELEGRAM,
            str(telegram_id),
            verified_at=utcnow(),
        )

    async def create_link_request(self, telegram_id: int) -> tuple[str, datetime]:
        """Выдать одноразовый код привязки. Повторный вызов перевыпускает код."""
        if await self._get_telegram_identity(telegram_id) is not None:
            raise TelegramAlreadyLinkedError(telegram_id)

        code = _generate_code()
        expires_at = utcnow() + LINK_CODE_TTL

        request = await self.link_repo.get_by_telegram_id(telegram_id)
        if request is None:
            await self.link_repo.create(telegram_id, hash_code(code), expires_at)
        else:
            request.code_hash = hash_code(code)
            request.expires_at = expires_at
            await self.link_repo.save()

        return code, expires_at

    async def confirm_link(self, user, code: str) -> int:
        """Подтверждение кода залогиненным пользователем (из веба)."""
        request = await self.link_repo.get_by_code_hash(hash_code(code.strip().upper()))

        if request is None or request.expires_at < utcnow():
            raise LinkCodeInvalidError(code)

        # telegram уже привязан к кому-то, либо у учётки уже есть Telegram.
        if await self._get_telegram_identity(request.telegram_id) is not None:
            raise TelegramAlreadyLinkedError(request.telegram_id)
        if any(
            identity.provider == AuthProvider.TELEGRAM
            for identity in await self.identity_repo.list_user_identities(user.id)
        ):
            raise TelegramAlreadyLinkedError(request.telegram_id)

        await self.identity_repo.add_identity(
            user.id,
            AuthProvider.TELEGRAM,
            str(request.telegram_id),
            verified_at=utcnow(),
        )
        await self.link_repo.delete(request)

        return request.telegram_id

    async def unlink(self, user) -> None:
        identities = await self.identity_repo.list_user_identities(user.id)
        telegram_identities = [
            identity for identity in identities
            if identity.provider == AuthProvider.TELEGRAM
        ]

        if not telegram_identities:
            raise TelegramNotLinkedError(user.id)

        # Считаем только подтверждённые способы входа: почта, ожидающая
        # подтверждения кодом, войти пока не позволяет.
        usable = [identity for identity in identities if identity.verified_at is not None]
        if len(usable) <= 1:
            raise LastLoginMethodError(user.id)

        await self.identity_repo.delete_identity(telegram_identities[0])

    async def _get_telegram_identity(self, telegram_id: int) -> AuthIdentity | None:
        return await self.identity_repo.get_by_provider_external_id(
            AuthProvider.TELEGRAM, str(telegram_id)
        )
