import logging

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from src.core.portfolio_manager import PortfolioManager

from src.bot.texts import welcome_head
from src.bot.utils import check_links_exist
from src.bot.ui import welcome_user_answer, change_user_links_answer

from src.config import settings

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
        logging.log(20, f"Accounts: {accounts}")
        await change_user_links_answer(message, accounts, welcome_head)