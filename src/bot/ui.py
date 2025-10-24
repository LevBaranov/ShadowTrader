from datetime import datetime
from typing import List, Tuple
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import Message

from string import Template

from src.bot.texts import welcome_user, welcome_guest, free_cash, position, action, success, error_text, errors
from src.bot.texts import set_scheduler, set_tracking_index
from src.bot.texts import user_settings_text_template
from src.bot.utils import AccountCallbackFactory, BalanceActionsCallbackFactory, ActionsCallbackFactory
from src.bot.utils import ScheduleCallbackFactory, SetIndexCallbackFactory

from src.models.account import Account
from src.models.positions import Positions
from src.models.action import Action
from src.models.error import Error
from src.models.scheduler_frequency import ScheduleFrequency
from src.models.config import UserIndexBindingsConfig, UserConfig


#region Keys

def get_accounts_keys(accounts: List[Account]):
    builder = InlineKeyboardBuilder()
    for account in accounts:
        account_name = account.name if account.name else "Без названия"
        builder.button(
            text=account_name, callback_data=AccountCallbackFactory(action="set",
                                                                    account_id=account.id)
        )
    builder.adjust(2)
    return builder.as_markup()

def get_balance_actions_keys():
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Выполнить все действия", callback_data=BalanceActionsCallbackFactory(action="execute")
    )

    builder.adjust(2)
    return builder.as_markup()

def get_actions_keys():
    """
    Функция подготовки кнопок возможных действий бота
    :return:
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Выполнить балансировку", callback_data=ActionsCallbackFactory(action="rebalance")
    )
    builder.button(
        text="Проверить облигации", callback_data=ActionsCallbackFactory(action="check_bonds")
    )
    builder.button(
        text="Изменить привязку", callback_data=ActionsCallbackFactory(action="relinked")
    )

    builder.adjust(2)
    return builder.as_markup()

def get_scheduler_keys():
    builder = InlineKeyboardBuilder()
    for period in ScheduleFrequency:
        builder.button(
            text=period.value, callback_data=ScheduleCallbackFactory(frequency=period.name)
        )

    builder.button(
        text="Никогда", callback_data=ScheduleCallbackFactory(frequency="NEVER")
    )
    builder.adjust(2)
    return builder.as_markup()

def get_indices_keys(indices: List[Tuple[str, str]]):
    builder = InlineKeyboardBuilder()

    for index, short_name in indices:

        builder.button(
            text=f"{short_name}({index})", callback_data=SetIndexCallbackFactory(index=index)
        )

    builder.adjust(1)
    return builder.as_markup()

#endregion Keys

#region Message

async def welcome_user_answer(message: Message, index_bindings: UserIndexBindingsConfig, message_header: str = None):
    mes = Template(welcome_user).substitute(
        account_name=index_bindings.broker_account_name,
        index_name=index_bindings.index_name
    )
    if message_header:
        mes = message_header + mes
    await message.answer(mes, reply_markup=get_actions_keys())

async def change_user_index_bindings_answer(message: Message, accounts: List[Account], message_header: str = None):
    """
    Формирует и отправляет сообщение по шаблону для настройки связки между аккаунтом пользователя и индексом Мосбиржи
    :param message: Сообщение для ответа и отправки сообщения
    :param accounts: Аккаунт пользователя у брокера
    :param message_header: Заголовок сообщения
    :return:
    """
    markup = get_accounts_keys(accounts)
    mes = Template(welcome_guest).substitute(
        accounts_count=len(accounts)
    )
    if message_header:
        mes = message_header + mes
    await message.answer(mes, reply_markup=markup)

async def portfolio_structure_message(message: Message, portfolio: Positions):
    mes = (Template(free_cash).substitute(cash=portfolio.cash.to_float()) +
               "\n".join([Template(position).substitute(ticker=pos.ticker, balance=pos.balance)
                          for pos in portfolio.shares]))
    await message.answer(mes)

async def actions_list_message(message: Message, actions: List[Action]):
    mes = "\n".join(
            [Template(action).substitute(
                type=act.type, ticker=act.share.ticker, count=act.quantity) for act in actions
            ])
    await message.answer(mes, reply_markup=get_balance_actions_keys())

async def actions_result_message(message: Message, success_action_list: List[Action], error_action_list: List[Error]):
    success_message = success + "\n".join(
        [Template(action).substitute(
            ticker=success_action.share.ticker, type=success_action.type, count=success_action.quantity)
            for success_action in success_action_list
        ])

    error_message = errors + "\n".join(
        [Template(error_text).substitute(
            ticker=error.data.share.ticker, error=error.description) for error in error_action_list
        ])
    mes = f"{success_message}\n{error_message}"
    await message.answer(mes)

async def scheduler_setting_message(message: Message):

    await message.answer(set_scheduler, reply_markup=get_scheduler_keys())

async def tracking_index_setting_message(message: Message, indices: List[Tuple[str, str]]):

    await message.answer(set_tracking_index, reply_markup=get_indices_keys(indices))

async def user_settings_message(message: Message, user_settings: UserConfig):
    """
    Формирует и отправляет сообщение по шаблону с настройками пользователя
    :param message: Сообщение для ответа
    :param user_settings: Пользовательские настройки
    :return:
    """
    frequency = ScheduleFrequency[user_settings.schedule.rebalance_frequency]
    last_run = user_settings.schedule.last_run.date()
    mes = Template(user_settings_text_template).substitute(
        telegram_id=user_settings.telegram_id,
        broker_account_name=user_settings.index_bindings.broker_account_name,
        index_name=user_settings.index_bindings.index_name,
        rebalance_frequency=frequency.value,
        last_run=last_run
    )
    await message.answer(mes)

#endregion Message