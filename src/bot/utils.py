from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.state import StatesGroup, State

from src.config import settings
from src.config.base import UserLinksConfig


class AccountCallbackFactory(CallbackData, prefix="account"):
    action: str
    account_id: str

class BalanceActionsCallbackFactory(CallbackData, prefix="balance_actions"):
    action: str

class ActionsCallbackFactory(CallbackData, prefix="actions"):
    action: str

class ScheduleCallbackFactory(CallbackData, prefix="schedule"):
    frequency: str

class SetIndexCallbackFactory(CallbackData, prefix="set_index"):
    index: str


class PortfolioRebalanceState(StatesGroup):
    get_actions = State()


def check_links_exist(user_id: int) -> UserLinksConfig:
    user = [ user for user in settings.users if user.telegram_id == user_id]

    if (user[0].links
            and user[0].links.index_name
            and user[0].links.broker_account_id
            and user[0].links.broker_account_name):
        return user[0].links
    else:
        return None
