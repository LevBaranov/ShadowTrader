import logging

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from src.core.portfolio_manager import PortfolioManager

from src.config import settings

from src.bot.texts import welcome_head
from src.bot.utils import check_index_bindings_exist
from src.bot.ui import welcome_user_answer, change_user_index_bindings_answer, user_settings_message

from src.db.database import get_session
from src.db.repositories.task_repository import TaskRepository

router = Router()
router.message.filter(F.chat.id.in_([user.telegram_id for user in settings.users]))


@router.message(Command("start"))
async def cmd_start(message: Message):


    index_bindings = check_index_bindings_exist(message.from_user.id)
    if index_bindings:
        await welcome_user_answer(message, index_bindings, welcome_head)
    else:
        manager = PortfolioManager()
        accounts = manager.get_user_accounts()
        await change_user_index_bindings_answer(message, accounts, welcome_head)


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    """
    Логика выполнения команды /settings.
    Если связка для отслеживания задана, то возвращаем текущую связку и когда было выполнено последнее задание
    по расписанию.
    Если связка для отслеживания не задана, то предлагаем настроить.
    :param message:
    :return:
    """

    index_bindings = check_index_bindings_exist(message.from_user.id)
    if index_bindings:
        user_settings = [user for user in settings.users if user.telegram_id == message.from_user.id][0]
        bond_last_checked_date = None
        if user_settings.bonds_account:
            async for session in get_session():
                repo = TaskRepository(session)
                tasks = await repo.get_user_tasks(
                    user_telegram_id=message.from_user.id,
                    broker_account_id=user_settings.bonds_account.broker_account_id
                )

                for _t in tasks:
                    bond_last_checked_date = _t.last_checked_date
                    break


        await user_settings_message(message, user_settings, bond_last_checked_date)
    else:
        manager = PortfolioManager()
        accounts = manager.get_user_accounts()
        await change_user_index_bindings_answer(message, accounts, welcome_head)