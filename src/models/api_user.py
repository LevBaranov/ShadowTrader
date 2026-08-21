from decimal import Decimal
from typing import List

from pydantic import EmailStr, Field

from src.models.api_base import BaseApiModel
from src.models.rebalance import PortfolioPosition

class BaseInfo(BaseApiModel):
    id: str
    name: str

class BrokerInfoStrategy(BaseInfo):
    account: BaseInfo
    # Комиссия брокера долей (0.003 = 0,3 %) — участвует в расчёте балансировки,
    # поэтому отдаём вместе со стратегией. Правится через PATCH /brokers/{id}.
    commission: Decimal = Decimal("0")

class StrategyListItem(BaseApiModel):
    """Лёгкий элемент списка стратегий — без портфеля и похода к брокеру."""
    id: str
    broker_info: BrokerInfoStrategy
    index_info: BaseInfo
    # PK счёта в нашей БД — им параметризуются задачи (BOND_EVENTS_MONITOR).
    brokers_account_id: str
    account_deleted: bool = False
    # Настройки расчёта здесь не дублируем: у списка одна задача — выбрать
    # стратегию. Полная карточка с настройками — в UserStrategy (GET /users/me).


class StrategySettings(BaseApiModel):
    """Настройки расчёта, которые пользователь правит на карточке стратегии.

    delta — доля (0.05 = 5 %); проценты для пользователя считает клиент.
    Комиссии здесь нет: это тариф брокера, приходит в broker_info.
    """
    max_cash: int = 0
    delta: Decimal
    min_lots_to_keep: int


class UserStrategy(BaseApiModel):
    id: str
    broker_info: BrokerInfoStrategy
    index_info: BaseInfo
    portfolio: List[PortfolioPosition | None]
    # Свободные средства сейчас и сколько останется после применения стратегии.
    free_cash: float
    free_cash_after: float
    # Настройки расчёта — их правят на карточке стратегии.
    settings: StrategySettings
    # Счёт стратегии помечен удалённым у брокера — балансировка недоступна.
    account_deleted: bool = False

class CurrentUserInfo(BaseApiModel):
    id: str
    # None у пользователей, зарегистрированных только через Telegram.
    email: str | None
    telegram_linked: bool = False
    strategies: List[UserStrategy]


class RebalanceRequest(BaseApiModel):
    strategy_id: str


class LoginRequest(BaseApiModel):
    email: str
    password: str

class LoginSuccess(BaseApiModel):
    access_token: str
    token_type: str


class RegisterRequest(BaseApiModel):
    email: EmailStr
    password: str = Field(min_length=6)

class ChangeEmailRequest(BaseApiModel):
    email: EmailStr
    # Обязателен, только если у пользователя ещё нет входа по почте
    # (регистрация была через Telegram).
    password: str | None = Field(default=None, min_length=6)

class ChangeEmailConfirmRequest(BaseApiModel):
    code: str

class PendingEmailResponse(BaseApiModel):
    """Адрес, на который отправлен код подтверждения."""
    pending_email: str

class ConfirmEmailRequest(BaseApiModel):
    email: EmailStr
    code: str

class ResendCodeRequest(BaseApiModel):
    email: EmailStr

class RegisterSuccess(BaseApiModel):
    email: str

