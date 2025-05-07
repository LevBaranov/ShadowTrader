import logging
from string import Template

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from core.portfolio_manager import PortfolioManager

from bot.texts import welcome
from bot.utils import get_accounts_keys

from config import settings

router = Router()
router.message.filter(F.chat.id.in_([user.telegram_id for user in settings.users]))


@router.message(Command("start"))
async def cmd_start(message: Message):

    manager = PortfolioManager()
    accounts = manager.get_user_accounts()
    logging.log(20, f"Accounts: {accounts}")
    markup = get_accounts_keys(accounts)
    mes = Template(welcome).substitute(
        accounts_count=len(accounts)
    )

    await message.answer(mes, reply_markup=markup)