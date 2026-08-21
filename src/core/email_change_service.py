"""Смена (или добавление) почты с подтверждением кодом.

Новая почта заводится как вторая, ещё не подтверждённая EMAIL-identity: адрес
сразу занят за пользователем, а старый способ входа продолжает работать, пока
код не подтверждён. На подтверждении новая identity становится verified, а
прежняя удаляется.

Пользователь, зарегистрированный только через Telegram, так же добавляет себе
вход по почте — тогда вместе с адресом нужен пароль.
"""
from src.core.verification import (
    ResendCooldownError,
    can_resend,
    issue_code,
    mark_verified,
    normalize_email,
    verify_code,
)
from src.db.enums import AuthProvider
from src.db.models.auth_identity import AuthIdentity

CHANGE_EMAIL_SUBJECT = "Подтверждение почты — ShadowTrader"
CHANGE_EMAIL_BODY = (
    "Ваш код подтверждения новой почты: {code}\n\n"
    "Код действует 15 минут.\n"
    "Если вы не меняли почту в ShadowTrader, просто проигнорируйте это письмо."
)


class EmailAlreadyTakenError(Exception):
    """Адрес уже занят другой учётной записью."""


class EmailUnchangedError(Exception):
    """Указан тот же адрес, что уже подтверждён у пользователя."""


class PasswordRequiredError(Exception):
    """У пользователя ещё нет входа по почте — вместе с адресом нужен пароль."""


class NoPendingEmailError(Exception):
    """Нет начатой смены почты (нечего подтверждать/переотправлять)."""


class EmailChangeService:

    def __init__(self, identity_repo, email_service, password_hasher):
        self.identity_repo = identity_repo
        self.email_service = email_service
        self.password_hasher = password_hasher

    async def request_change(self, user, new_email: str, password: str | None = None) -> str:
        """Начать смену почты: занять адрес и отправить на него код."""
        email = normalize_email(new_email)

        verified, pending = await self._email_identities(user.id)

        if verified is not None and verified.external_id == email:
            raise EmailUnchangedError(email)

        occupied = await self.identity_repo.get_by_provider_external_id(
            AuthProvider.EMAIL, email
        )
        if occupied is not None and occupied.user_id != user.id:
            raise EmailAlreadyTakenError(email)

        if verified is not None:
            # Пароль переносим со старой identity: после подтверждения она удалится.
            password_hash = verified.password_hash
        elif password:
            password_hash = self.password_hasher(password)
        else:
            raise PasswordRequiredError(email)

        if pending is None:
            pending = await self.identity_repo.add_identity(
                user.id,
                AuthProvider.EMAIL,
                email,
                password_hash=password_hash,
            )
        else:
            pending.external_id = email
            pending.password_hash = password_hash

        await issue_code(
            pending,
            self.identity_repo,
            self.email_service,
            CHANGE_EMAIL_SUBJECT,
            CHANGE_EMAIL_BODY,
        )

        return email

    async def confirm_change(self, user, code: str) -> str:
        """Подтвердить новую почту и убрать прежнюю."""
        verified, pending = await self._email_identities(user.id)

        if pending is None or not pending.verification_code_hash:
            raise NoPendingEmailError(user.id)

        await verify_code(pending, code, self.identity_repo)
        await mark_verified(pending, self.identity_repo)

        if verified is not None:
            await self.identity_repo.delete_identity(verified)

        return pending.external_id

    async def resend_code(self, user) -> str:
        _, pending = await self._email_identities(user.id)

        if pending is None:
            raise NoPendingEmailError(user.id)

        if not can_resend(pending):
            raise ResendCooldownError(pending.external_id)

        await issue_code(
            pending,
            self.identity_repo,
            self.email_service,
            CHANGE_EMAIL_SUBJECT,
            CHANGE_EMAIL_BODY,
        )

        return pending.external_id

    async def cancel_change(self, user) -> None:
        """Отменить начатую смену: освободить занятый адрес."""
        verified, pending = await self._email_identities(user.id)

        if pending is None:
            raise NoPendingEmailError(user.id)

        if verified is None:
            # Отменять нечего в пользу чего: это единственная почта пользователя,
            # удалять её нельзя — просто гасим код.
            pending.verification_code_hash = None
            pending.verification_code_expires_at = None
            pending.verification_attempts = 0
            await self.identity_repo.save()
            return

        await self.identity_repo.delete_identity(pending)

    async def _email_identities(
        self, user_id
    ) -> tuple[AuthIdentity | None, AuthIdentity | None]:
        """Подтверждённая и ожидающая подтверждения EMAIL-identity пользователя."""
        identities = await self.identity_repo.list_user_identities(user_id)

        verified = None
        pending = None
        for identity in identities:
            if identity.provider != AuthProvider.EMAIL:
                continue
            if identity.verified_at is None:
                pending = identity
            else:
                verified = identity

        return verified, pending
