from decimal import Decimal

from pydantic import Field

from src.models.api_base import BaseApiModel
from src.models.broker_names import BrokerNames

# Комиссия в контракте — доля, а не проценты: 0.003 = 0,3 %.
# lt=1 отсекает случай, когда клиент прислал проценты вместо доли.
CommissionField = Field(ge=0, lt=1)


class BrokerSettingsRequest(BaseApiModel):
    broker_name: BrokerNames
    token: str
    sandbox: bool = False
    # None — не менять: у нового брокера останется значение по умолчанию (0.003),
    # у существующего — уже сохранённое.
    commission: Decimal | None = Field(default=None, ge=0, lt=1)


class UpdateBrokerRequest(BaseApiModel):
    """Настройки брокера без секретов — правятся отдельно от токена."""
    commission: Decimal = CommissionField


class BrokerSettingsResponse(BaseApiModel):
    id: str
    broker_name: BrokerNames
    sandbox: bool
    # Доля: 0.003 = 0,3 %. Проценты для пользователя считает клиент.
    commission: Decimal


class BrokerAccountResponse(BaseApiModel):
    id: str            # PK аккаунта в нашей БД (используется при создании стратегии)
    account_id: str    # идентификатор счёта на стороне брокера
    account_name: str
    has_strategy: bool = False  # на счёте уже есть стратегия — вторую создать нельзя


class AccountResponse(BrokerAccountResponse):
    """Счёт в плоском списке всех счетов пользователя — с информацией о брокере."""
    broker_id: str
    broker_name: BrokerNames
    sandbox: bool = False
