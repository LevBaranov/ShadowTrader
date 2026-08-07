import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.bond import get_bond_service
from src.core.bond_service import BondService, AccountNotFoundError
from src.models.api_bond import BondEventResponse, BondWithEventsResponse

router = APIRouter(prefix="/bonds")


@router.get("/events", response_model=list[BondWithEventsResponse])
async def get_bond_events(
    brokers_account_id: uuid.UUID = Query(alias="brokersAccountId"),
    current_user=Depends(get_current_user),
    bond_service: BondService = Depends(get_bond_service),
) -> list[BondWithEventsResponse]:
    """Облигации на счёте, по которым впереди оферта или колл-опцион.

    Счёт выбирает пользователь — любой свой, со стратегиями это не связано.
    """
    try:
        bonds = await bond_service.get_bond_events(current_user, brokers_account_id)
    except AccountNotFoundError:
        raise HTTPException(status_code=404, detail="account_not_found")

    return [
        BondWithEventsResponse(
            ticker=bond.ticker,
            name=bond.short_name,
            figi=bond.figi,
            quantity=bond.balance,
            events=[
                BondEventResponse(type=event.type.name, date=event.date)
                for event in bond.events
            ],
        )
        for bond in bonds
    ]
