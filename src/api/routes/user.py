from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.email_change import get_email_change_service
from src.api.dependencies.notification_settings import get_notification_settings_service
from src.api.dependencies.strategy import get_strategy_service
from src.api.dependencies.telegram_link import get_telegram_link_service
from src.core.notification_settings_service import (
    NotificationSettingsService,
    NotificationChannelUnavailableError,
)
from src.core.email_change_service import (
    EmailChangeService,
    EmailAlreadyTakenError,
    EmailUnchangedError,
    NoPendingEmailError,
    PasswordRequiredError,
)
from src.core.telegram_link_service import (
    TelegramLinkService,
    TelegramNotLinkedError,
    TelegramAlreadyLinkedError,
    LinkCodeInvalidError,
    LastLoginMethodError,
)
from src.core.user_service import UserService
from src.core.verification import (
    CodeExpiredError,
    InvalidCodeError,
    ResendCooldownError,
    TooManyAttemptsError,
)
from src.models.api_telegram import (
    NotificationChannelRequest,
    TelegramLinkConfirmRequest,
    TelegramLinkResponse,
    UserProfile,
)
from src.models.api_user import (
    ChangeEmailConfirmRequest,
    ChangeEmailRequest,
    CurrentUserInfo,
    PendingEmailResponse,
)
from src.services.email import EmailSendError

router = APIRouter(prefix="/users")


def _profile_response(user) -> UserProfile:
    return UserProfile(
        email=user.email,
        pending_email=user.pending_email,
        telegram_linked=user.telegram_id is not None,
        notification_channel=user.notification_channel,
    )


@router.get("/me", response_model=CurrentUserInfo)
async def get_me(
        current_user=Depends(get_current_user),
        strategy_service: UserService = Depends(get_strategy_service)
):
    user_strategies = await strategy_service.get_user_strategies(current_user)

    return CurrentUserInfo(
        id=str(current_user.id),
        email=current_user.email,
        telegram_linked=current_user.telegram_id is not None,
        strategies=user_strategies
    )


@router.get("/me/profile", response_model=UserProfile)
async def get_profile(current_user=Depends(get_current_user)) -> UserProfile:
    """Лёгкий профиль без похода к брокеру — для бота и шапки фронта."""
    return _profile_response(current_user)


@router.patch("/me/notifications", response_model=UserProfile)
async def set_notification_channel(
    data: NotificationChannelRequest,
    current_user=Depends(get_current_user),
    service: NotificationSettingsService = Depends(get_notification_settings_service),
) -> UserProfile:
    """Куда отправлять уведомления планировщика: Telegram, почта или оба канала."""
    try:
        user = await service.set_channel(current_user, data.channel)
    except NotificationChannelUnavailableError as error:
        raise HTTPException(status_code=409, detail=str(error))

    return _profile_response(user)


@router.post("/me/email", response_model=PendingEmailResponse)
async def request_email_change(
    data: ChangeEmailRequest,
    current_user=Depends(get_current_user),
    service: EmailChangeService = Depends(get_email_change_service),
) -> PendingEmailResponse:
    """Начать смену (или добавление) почты: код уходит на новый адрес."""
    try:
        email = await service.request_change(current_user, data.email, data.password)
    except EmailUnchangedError:
        raise HTTPException(status_code=409, detail="email_unchanged")
    except EmailAlreadyTakenError:
        raise HTTPException(status_code=409, detail="email_already_registered")
    except PasswordRequiredError:
        raise HTTPException(status_code=422, detail="password_required")
    except EmailSendError:
        raise HTTPException(status_code=503, detail="email_send_failed")

    return PendingEmailResponse(pending_email=email)


@router.post("/me/email/confirm", response_model=UserProfile)
async def confirm_email_change(
    data: ChangeEmailConfirmRequest,
    current_user=Depends(get_current_user),
    service: EmailChangeService = Depends(get_email_change_service),
) -> UserProfile:
    """Подтвердить новую почту кодом из письма."""
    try:
        email = await service.confirm_change(current_user, data.code)
    except NoPendingEmailError:
        raise HTTPException(status_code=404, detail="no_pending_email")
    except InvalidCodeError:
        raise HTTPException(status_code=400, detail="invalid_code")
    except CodeExpiredError:
        raise HTTPException(status_code=400, detail="code_expired")
    except TooManyAttemptsError:
        raise HTTPException(status_code=429, detail="too_many_attempts")

    return UserProfile(
        email=email,
        pending_email=None,
        telegram_linked=current_user.telegram_id is not None,
        notification_channel=current_user.notification_channel,
    )


@router.post("/me/email/resend", response_model=PendingEmailResponse)
async def resend_email_change_code(
    current_user=Depends(get_current_user),
    service: EmailChangeService = Depends(get_email_change_service),
) -> PendingEmailResponse:
    try:
        email = await service.resend_code(current_user)
    except NoPendingEmailError:
        raise HTTPException(status_code=404, detail="no_pending_email")
    except ResendCooldownError:
        raise HTTPException(status_code=429, detail="resend_cooldown")
    except EmailSendError:
        raise HTTPException(status_code=503, detail="email_send_failed")

    return PendingEmailResponse(pending_email=email)


@router.delete("/me/email/pending", status_code=204)
async def cancel_email_change(
    current_user=Depends(get_current_user),
    service: EmailChangeService = Depends(get_email_change_service),
) -> None:
    """Отменить начатую смену почты (освобождает занятый адрес)."""
    try:
        await service.cancel_change(current_user)
    except NoPendingEmailError:
        raise HTTPException(status_code=404, detail="no_pending_email")


@router.post("/me/telegram-link", response_model=TelegramLinkResponse)
async def confirm_telegram_link(
    data: TelegramLinkConfirmRequest,
    current_user=Depends(get_current_user),
    service: TelegramLinkService = Depends(get_telegram_link_service),
) -> TelegramLinkResponse:
    try:
        telegram_id = await service.confirm_link(current_user, data.code)
    except LinkCodeInvalidError:
        raise HTTPException(status_code=400, detail="invalid_code")
    except TelegramAlreadyLinkedError:
        raise HTTPException(status_code=409, detail="telegram_already_linked")

    return TelegramLinkResponse(telegram_id=telegram_id)


@router.delete("/me/telegram-link", status_code=204)
async def unlink_telegram(
    current_user=Depends(get_current_user),
    service: TelegramLinkService = Depends(get_telegram_link_service),
) -> None:
    try:
        await service.unlink(current_user)
    except TelegramNotLinkedError:
        raise HTTPException(status_code=404, detail="telegram_not_linked")
    except LastLoginMethodError:
        raise HTTPException(status_code=409, detail="last_login_method")
