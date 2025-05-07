from string import Template

from aiogram import Router, F
from aiogram.types import CallbackQuery

from core.portfolio_manager import PortfolioManager

from bot.utils import AccountCallbackFactory
from bot.texts import action

from config import settings

router = Router()
router.callback_query.filter(F.from_user.id.in_([user.telegram_id for user in settings.users]))

@router.callback_query(AccountCallbackFactory.filter())
async def callbacks_account(
        callback: CallbackQuery,
        callback_data: AccountCallbackFactory
):

    account_id = callback_data.value
    manager = PortfolioManager(account_id)
    portfolio = manager.get_portfolio()
    index_moex = manager.get_index_list(settings.stock_market.index_name)

    actions, cash = manager.get_action_for_rebalance(portfolio, index_moex)

    message = "\n".join(
        [Template(action).substitute(
            type=act.type, ticker=act.share.ticker, count=act.quantity) for act in actions
        ])
    await callback.message.answer(message)
    await callback.answer()

