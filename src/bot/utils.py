from typing import List, Tuple

from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.state import StatesGroup, State

from src.config import settings
from src.config.base import UserLinksConfig
from src.core.portfolio_manager import PortfolioManager
from src.models import Action, Positions

class AccountCallbackFactory(CallbackData, prefix="account"):
    action: str
    account_id: str

class BalanceActionsCallbackFactory(CallbackData, prefix="balance_actions"):
    action: str

class ActionsCallbackFactory(CallbackData, prefix="actions"):
    action: str

class ScheduleCallbackFactory(CallbackData, prefix="schedule"):
    frequency: str


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

def get_actions_list(manager: PortfolioManager, index_name: str) -> Tuple[Positions, List[Action], float]:
    portfolio = manager.get_portfolio()

    index_moex = manager.get_index_list(index_name)
    actions, new_balance = manager.get_action_for_rebalance(portfolio, index_moex)

    return portfolio, actions, new_balance