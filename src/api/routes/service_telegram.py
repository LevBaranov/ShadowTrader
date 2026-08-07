from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies.service_auth import require_service_key
from src.api.dependencies.telegram_link import get_telegram_link_service
from src.api.security import create_access_token
from src.config import api_settings
from src.core.telegram_link_service import (
    TelegramLinkService,
    TelegramNotLinkedError,
    TelegramAlreadyLinkedError,
)
from src.models.api_telegram import (
    TelegramIdRequest,
    ServiceTokenResponse,
    TelegramRegisterResponse,
    LinkRequestResponse,
)

router = APIRouter(
    prefix="/service/telegram",
    dependencies=[Depends(require_service_key)],
)


@router.post("/token", response_model=ServiceTokenResponse)
async def issue_token(
    data: TelegramIdRequest,
    service: TelegramLinkService = Depends(get_telegram_link_service),
) -> ServiceTokenResponse:
    try:
        user_id = await service.get_linked_user_id(data.telegram_id)
    except TelegramNotLinkedError:
        raise HTTPException(status_code=404, detail="telegram_not_linked")

    expires_minutes = api_settings.SERVICE_TOKEN_EXPIRE_MINUTES
    token = create_access_token(str(user_id), expires_minutes=expires_minutes)

    return ServiceTokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_minutes * 60,
    )


@router.post("/register", response_model=TelegramRegisterResponse, status_code=201)
async def register_telegram_user(
    data: TelegramIdRequest,
    service: TelegramLinkService = Depends(get_telegram_link_service),
) -> TelegramRegisterResponse:
    try:
        identity = await service.register_telegram_user(data.telegram_id)
    except TelegramAlreadyLinkedError:
        raise HTTPException(status_code=409, detail="telegram_already_linked")

    return TelegramRegisterResponse(user_id=str(identity.user_id))


@router.post("/link-requests", response_model=LinkRequestResponse)
async def create_link_request(
    data: TelegramIdRequest,
    service: TelegramLinkService = Depends(get_telegram_link_service),
) -> LinkRequestResponse:
    try:
        code, expires_at = await service.create_link_request(data.telegram_id)
    except TelegramAlreadyLinkedError:
        raise HTTPException(status_code=409, detail="telegram_already_linked")

    return LinkRequestResponse(code=code, expires_at=expires_at)
