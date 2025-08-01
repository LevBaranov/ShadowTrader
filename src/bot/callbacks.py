from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from src.core.portfolio_manager import PortfolioManager

from src.bot.utils import AccountCallbackFactory, ActionsCallbackFactory, BalanceActionsCallbackFactory
from src.bot.utils import ScheduleCallbackFactory, SetIndexCallbackFactory
from src.bot.utils import PortfolioRebalanceState, get_actions_list

from src.bot.ui import actions_list_message, actions_result_message, welcome_user_answer, tracking_index_setting_message
from src.bot.ui import change_user_links_answer, portfolio_structure_message, scheduler_setting_message

from src.config import settings, ConfigLoader

router = Router()
router.callback_query.filter(F.from_user.id.in_([user.telegram_id for user in settings.users]))


@router.callback_query(AccountCallbackFactory.filter())
async def callbacks_account(
        callback: CallbackQuery,
        callback_data: AccountCallbackFactory
):

    account_id = callback_data.account_id
    manager = PortfolioManager()
    account = [acc for acc in manager.get_user_accounts() if acc.id == account_id]

    ConfigLoader.update_broker_account(callback.from_user.id, account_id, account[0].name)
    updated_settings = ConfigLoader.config
    await tracking_index_setting_message(callback.message, manager.get_indices_list())
    await callback.answer()


@router.callback_query(SetIndexCallbackFactory.filter())
async def callbacks_account(
        callback: CallbackQuery,
        callback_data: SetIndexCallbackFactory
):

    ConfigLoader.update_tracking_index(callback.from_user.id, callback_data.index)
    updated_settings = ConfigLoader.config
    await scheduler_setting_message(callback.message)
    await callback.answer()


@router.callback_query(ScheduleCallbackFactory.filter())
async def callbacks_account(
        callback: CallbackQuery,
        callback_data: ScheduleCallbackFactory
):

    ConfigLoader.update_schedule(callback.from_user.id, callback_data.frequency)
    updated_settings = ConfigLoader.config
    await welcome_user_answer(callback.message, settings.users[0].links)
    await callback.answer()


@router.callback_query(ActionsCallbackFactory.filter())
async def callbacks_account(
            callback: CallbackQuery,
            callback_data: ActionsCallbackFactory,
            state: FSMContext
):
    user = [user for user in settings.users if user.telegram_id == callback.from_user.id][0]
    if callback_data.action == "rebalance":
        account_id = user.links.broker_account_id
        manager = PortfolioManager(account_id)
        portfolio, actions, cash = get_actions_list(manager, user.links.index_name)

        await portfolio_structure_message(callback.message, portfolio)
        await state.update_data(manager=manager)

        await actions_list_message(callback.message, actions)
        await callback.answer()
        await state.set_state(PortfolioRebalanceState.get_actions)
    else:
        manager = PortfolioManager()
        accounts = manager.get_user_accounts()
        await change_user_links_answer(callback.message, accounts)
        await callback.answer()


@router.callback_query(BalanceActionsCallbackFactory.filter())
async def callbacks_account(
        callback: CallbackQuery,
        callback_data: BalanceActionsCallbackFactory,
        state: FSMContext
):
    state_data = await state.get_data()
    manager: PortfolioManager = state_data.get("manager")
    success_action_list, error_action_list = manager.execute_actions()

    await actions_result_message(callback.message, success_action_list, error_action_list)
    await callback.answer()
    await state.clear()

