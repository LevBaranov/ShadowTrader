from src.models.api_base import BaseApiModel
from src.models.broker_names import BrokerNames


class BrokerSettingsRequest(BaseApiModel):
    broker_name: BrokerNames
    token: str
    sandbox: bool = False


class BrokerSettingsResponse(BaseApiModel):
    id: str
    broker_name: BrokerNames
    sandbox: bool


class BrokerAccountResponse(BaseApiModel):
    id: str            # PK аккаунта в нашей БД (используется при создании стратегии)
    account_id: str    # идентификатор счёта на стороне брокера
    account_name: str
    has_strategy: bool = False  # на счёте уже есть стратегия — вторую создать нельзя
