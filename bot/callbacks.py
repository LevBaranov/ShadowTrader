from string import Template

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from core.portfolio_manager import PortfolioManager

from bot.utils import AccountCallbackFactory, PortfolioRebalanceState, ActionsCallbackFactory, get_actions_keys
from bot.texts import action, free_cash, position, success, error_text, errors

from config import settings

router = Router()
router.callback_query.filter(F.from_user.id.in_([user.telegram_id for user in settings.users]))


@router.callback_query(AccountCallbackFactory.filter())
async def callbacks_account(
        callback: CallbackQuery,
        callback_data: AccountCallbackFactory,
        state: FSMContext
):

    account_id = callback_data.value
    manager = PortfolioManager(account_id)
    portfolio = manager.get_portfolio()
    message = (Template(free_cash).substitute(cash=portfolio.cash.to_float()) +
               "\n".join([Template(position).substitute(ticker=pos.ticker, balance=pos.balance)
                          for pos in portfolio.shares]))
    await callback.message.answer(message)
    index_moex = manager.get_index_list(settings.stock_market.index_name)

    actions, cash = manager.get_action_for_rebalance(portfolio, index_moex)

    await state.update_data(manager=manager)
    message = "\n".join(
        [Template(action).substitute(
            type=act.type, ticker=act.share.ticker, count=act.quantity) for act in actions
        ])
    await callback.message.answer(message, reply_markup=get_actions_keys())
    await callback.answer()
    await state.set_state(PortfolioRebalanceState.get_actions)


@router.callback_query(ActionsCallbackFactory.filter())
async def callbacks_account(
        callback: CallbackQuery,
        callback_data: ActionsCallbackFactory,
        state: FSMContext
):
    state_data = await state.get_data()
    manager: PortfolioManager = state_data.get("manager")
    success_action_list, error_action_list = manager.execute_actions()

    success_message = success + "\n".join(
        [Template(action).substitute(
            ticker=success_action.share.ticker, type=success_action.type, count=success_action.quantity)
            for success_action in success_action_list
        ])

    error_message = errors + "\n".join(
        [Template(error_text).substitute(
            ticker = error.data.share.ticker, error=error.description) for error in error_action_list
        ])

    await callback.message.answer(f"{success_message}\n{error_message}")
    await callback.answer()
    await state.clear()

