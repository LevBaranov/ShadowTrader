"""Плоский список счетов пользователя — по всем его брокерам.

Отдельно от /brokers/{id}/accounts: там счета нужны в контексте конкретного
брокера (создание стратегии), здесь — просто «все мои счета» (выбор счёта для
проверки облигаций, раздел настроек).
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.broker import get_broker_service
from src.core.broker_service import BrokerService
from src.models.api_broker import AccountResponse
from src.services.broker import BrokerAuthError

router = APIRouter(prefix="/accounts")

INVALID_TOKEN_DETAIL = "Токен брокера недействителен"


async def _response(broker_service: BrokerService, accounts) -> List[AccountResponse]:
    busy_ids = await broker_service.get_busy_account_ids(accounts)

    return [
        AccountResponse(
            id=str(account.id),
            account_id=account.account_id,
            account_name=account.account_name,
            has_strategy=account.id in busy_ids,
            broker_id=str(account.users_broker.id),
            broker_name=account.users_broker.broker_name,
            sandbox=account.users_broker.sandbox,
        )
        for account in accounts
    ]


@router.get("", response_model=List[AccountResponse])
async def list_accounts(
    current_user=Depends(get_current_user),
    broker_service: BrokerService = Depends(get_broker_service),
) -> List[AccountResponse]:
    """Все счета пользователя у всех подключённых брокеров."""
    try:
        accounts = await broker_service.list_all_accounts(current_user)
    except BrokerAuthError:
        raise HTTPException(status_code=422, detail=INVALID_TOKEN_DETAIL)

    return await _response(broker_service, accounts)


@router.post("/refresh", response_model=List[AccountResponse])
async def refresh_accounts(
    current_user=Depends(get_current_user),
    broker_service: BrokerService = Depends(get_broker_service),
) -> List[AccountResponse]:
    """Обновить счета по всем брокерам: новые появятся, закрытые исчезнут."""
    try:
        accounts = await broker_service.refresh_all_accounts(current_user)
    except BrokerAuthError:
        raise HTTPException(status_code=422, detail=INVALID_TOKEN_DETAIL)

    return await _response(broker_service, accounts)
