import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.broker import get_broker_service
from src.core.broker_service import (
    BrokerService,
    BrokerNotFoundError,
    BrokerValidationError,
)
from src.services.broker import BrokerAuthError

from src.models.api_broker import (
    BrokerSettingsRequest,
    BrokerSettingsResponse,
    BrokerAccountResponse,
    UpdateBrokerRequest,
)

INVALID_TOKEN_DETAIL = "Токен брокера недействителен"

router = APIRouter(prefix="/brokers")


def _broker_response(broker) -> BrokerSettingsResponse:
    return BrokerSettingsResponse(
        id=str(broker.id),
        broker_name=broker.broker_name,
        sandbox=broker.sandbox,
        commission=broker.commission,
    )


async def _accounts_response(
    broker_service: BrokerService, accounts
) -> List[BrokerAccountResponse]:
    busy_ids = await broker_service.get_busy_account_ids(accounts)
    return [
        BrokerAccountResponse(
            id=str(account.id),
            account_id=account.account_id,
            account_name=account.account_name,
            has_strategy=account.id in busy_ids,
        )
        for account in accounts
    ]


@router.put("", response_model=BrokerSettingsResponse)
async def save_broker_settings(
    body: BrokerSettingsRequest,
    current_user=Depends(get_current_user),
    broker_service: BrokerService = Depends(get_broker_service),
):
    """Сохранить (создать/обновить) настройки брокера пользователя.
    Токен шифруется на сервисном слое перед записью в БД и никогда не возвращается наружу.
    """
    try:
        broker = await broker_service.save_broker_settings(
            user=current_user,
            broker_name=body.broker_name,
            token=body.token,
            sandbox=body.sandbox,
            commission=body.commission,
        )
    except BrokerValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except BrokerAuthError:
        raise HTTPException(status_code=422, detail=INVALID_TOKEN_DETAIL)

    return _broker_response(broker)


@router.get("", response_model=List[BrokerSettingsResponse])
async def list_brokers(
    current_user=Depends(get_current_user),
    broker_service: BrokerService = Depends(get_broker_service),
):
    """Список брокеров пользователя (для выбора при создании стратегии)."""
    brokers = await broker_service.list_brokers(current_user)
    return [_broker_response(broker) for broker in brokers]


@router.patch("/{broker_id}", response_model=BrokerSettingsResponse)
async def update_broker(
    broker_id: uuid.UUID,
    body: UpdateBrokerRequest,
    current_user=Depends(get_current_user),
    broker_service: BrokerService = Depends(get_broker_service),
):
    """Настройки брокера без секретов: комиссия по тарифу.

    Отдельный эндпоинт, а не PUT: сохранение токена ходит в брокера на проверку,
    а правка комиссии не должна требовать повторного ввода токена.
    """
    try:
        broker = await broker_service.update_commission(
            current_user, broker_id, body.commission
        )
    except BrokerNotFoundError:
        raise HTTPException(status_code=404, detail="Broker not found")
    except BrokerValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return _broker_response(broker)


@router.get("/{broker_id}/accounts", response_model=List[BrokerAccountResponse])
async def get_broker_accounts(
    broker_id: uuid.UUID,
    current_user=Depends(get_current_user),
    broker_service: BrokerService = Depends(get_broker_service),
):
    """Список счетов пользователя у брокера.

    Читаются из БД; если их там ещё нет — подтягиваются из брокера и сохраняются
    в рамках этого же запроса.
    """
    try:
        accounts = await broker_service.get_broker_accounts(current_user, broker_id)
    except BrokerNotFoundError:
        raise HTTPException(status_code=404, detail="Broker not found")
    except BrokerAuthError:
        raise HTTPException(status_code=422, detail=INVALID_TOKEN_DETAIL)

    return await _accounts_response(broker_service, accounts)


@router.post("/{broker_id}/accounts/refresh", response_model=List[BrokerAccountResponse])
async def refresh_broker_accounts(
    broker_id: uuid.UUID,
    current_user=Depends(get_current_user),
    broker_service: BrokerService = Depends(get_broker_service),
):
    """Принудительно обновить счета из брокера.

    Новые счета создаются, пропавшие помечаются удалёнными (в выдачу не попадают).
    """
    try:
        accounts = await broker_service.refresh_broker_accounts(current_user, broker_id)
    except BrokerNotFoundError:
        raise HTTPException(status_code=404, detail="Broker not found")
    except BrokerAuthError:
        raise HTTPException(status_code=422, detail=INVALID_TOKEN_DETAIL)

    return await _accounts_response(broker_service, accounts)
