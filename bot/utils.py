from typing import List
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.state import StatesGroup, State


from models.account import Account

class AccountCallbackFactory(CallbackData, prefix="account"):
    action: str
    value: str

class ActionsCallbackFactory(CallbackData, prefix="actions"):
    action: str

def get_accounts_keys(accounts: List[Account]):
    builder = InlineKeyboardBuilder()
    for account in accounts:
        account_name = account.name if account.name else "Без названия"
        builder.button(
            text=account_name, callback_data=AccountCallbackFactory(action="set_account", value=account.id)
        )
    builder.adjust(2)
    return builder.as_markup()

def get_actions_keys():
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Выполнить все действия", callback_data=ActionsCallbackFactory(action="execute")
    )

    builder.adjust(2)
    return builder.as_markup()

class PortfolioRebalanceState(StatesGroup):
    get_actions = State()
