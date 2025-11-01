from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.state import StatesGroup, State

from src.config import settings

from src.models.config import UserIndexBindingsConfig, BrokerAccountConfig


class AccountCallbackFactory(CallbackData, prefix="account"):
    target: str
    account_id: str

class BalanceActionsCallbackFactory(CallbackData, prefix="balance_actions"):
    action: str

class ActionsCallbackFactory(CallbackData, prefix="actions"):
    action: str

class ScheduleCallbackFactory(CallbackData, prefix="schedule"):
    frequency: str

class SetIndexCallbackFactory(CallbackData, prefix="set_index"):
    index: str

class ReminderCallbackFactory(CallbackData, prefix="reminder"):
    enabled: bool

class SetCallableBondsAccountCallbackFactory(CallbackData, prefix="set_callable_bonds_account"):
    account_id: str


class PortfolioRebalanceState(StatesGroup):
    get_actions = State()


def check_index_bindings_exist(user_id: int) -> UserIndexBindingsConfig | None:
    """
    Проверяем наличие настроенной связки между аккаунтом в брокере и индексом Мосбиржи для пользователя.
    :param user_id: Идентификатор пользователя в телеграм
    :return: Информация по существующей связки пользователя
    """
    user = [ user for user in settings.users if user.telegram_id == user_id]

    if (user[0].index_bindings
            and user[0].index_bindings.index_name
            and user[0].index_bindings.broker_account_id):
        return user[0].index_bindings
    else:
        return None

def check_bonds_account_exist(user_id: int) -> BrokerAccountConfig | None:
    """
    Проверяем наличие настроенной связки между аккаунтом в брокере и индексом Мосбиржи для пользователя.
    :param user_id: Идентификатор пользователя в телеграм
    :return: Информация по существующей связки пользователя
    """
    user = [ user for user in settings.users if user.telegram_id == user_id]

    if (user[0].bonds_account
            and user[0].bonds_account.broker_account_id):
        return user[0].bonds_account
    else:
        return None
