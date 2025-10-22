import logging

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from src.core.portfolio_manager import PortfolioManager

from src.config import settings

from src.bot.texts import welcome_head
from src.bot.utils import check_links_exist
from src.bot.ui import welcome_user_answer, change_user_links_answer, user_settings_message


router = Router()
router.message.filter(F.chat.id.in_([user.telegram_id for user in settings.users]))


@router.message(Command("start"))
async def cmd_start(message: Message):


    links = check_links_exist(message.from_user.id)
    if links:
        await welcome_user_answer(message, links, welcome_head)
    else:
        manager = PortfolioManager()
        accounts = manager.get_user_accounts()
        await change_user_links_answer(message, accounts, welcome_head)


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

    links = check_links_exist(message.from_user.id)
    if links:
        user_settings = [user for user in settings.users if user.telegram_id == message.from_user.id][0]
        await user_settings_message(message, user_settings)
    else:
        manager = PortfolioManager()
        accounts = manager.get_user_accounts()
        await change_user_links_answer(message, accounts, welcome_head)