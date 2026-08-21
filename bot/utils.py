from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.state import StatesGroup, State


class MenuCb(CallbackData, prefix="menu"):
    # main | strategies | bonds | settings | signup | link | check_link |
    # new_strategy | brokers | add_broker | refresh_accounts | schedule |
    # change_email | resend_email_code | cancel_email | unlink_tg | unlink_tg_confirm
    section: str


class StrategyCb(CallbackData, prefix="st"):
    # view | exec | delete | confirm_delete | schedule
    action: str
    id: str


class BrokerCb(CallbackData, prefix="br"):
    # retoken — обновить токен доступа у подключённого брокера
    action: str
    id: str


class AccountCb(CallbackData, prefix="acc"):
    # Счёт выбирают в двух сценариях, поэтому таскаем цель выбора:
    # strategy — создание стратегии; bonds — проверка облигаций.
    purpose: str
    id: str


class RefreshAccountsCb(CallbackData, prefix="racc"):
    # Тот же purpose, что у AccountCb: куда вернуться после обновления списка.
    purpose: str


class IndexCb(CallbackData, prefix="idx"):
    id: str


class FreqCb(CallbackData, prefix="freq"):
    # WEEKLY | MONTHLY | QUARTERLY | SKIP
    frequency: str
    strategy_id: str


class ReminderCb(CallbackData, prefix="rem"):
    enable: bool
    # enable=True: brokers_account_id; enable=False: task_id
    target_id: str


class TaskCb(CallbackData, prefix="task"):
    # disable
    action: str
    id: str


class NewStrategyState(StatesGroup):
    waiting_broker_token = State()
    # Комиссия по тарифу — второй шаг подключения брокера, можно пропустить.
    waiting_broker_commission = State()


class BrokerCommissionState(StatesGroup):
    """Правка комиссии у уже подключённого брокера — без токена."""
    waiting_commission = State()


class EmailChangeState(StatesGroup):
    waiting_email = State()
    waiting_password = State()
    waiting_code = State()
