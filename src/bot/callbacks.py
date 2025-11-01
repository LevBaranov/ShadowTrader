from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from src.core.portfolio_manager import PortfolioManager

from src.config import settings, ConfigLoader

from src.bot.utils import AccountCallbackFactory, ActionsCallbackFactory, BalanceActionsCallbackFactory
from src.bot.utils import ScheduleCallbackFactory, SetIndexCallbackFactory, ReminderCallbackFactory
from src.bot.utils import SetCallableBondsAccountCallbackFactory
from src.bot.utils import PortfolioRebalanceState
from src.bot.utils import check_bonds_account_exist

from src.bot.ui import actions_list_message, actions_result_message, welcome_user_answer, tracking_index_setting_message
from src.bot.ui import change_user_index_bindings_answer, portfolio_structure_message, scheduler_setting_message
from src.bot.ui import account_callable_bonds_message, bonds_reminder_enabling_message
from src.bot.ui import callable_bonds_account_selecting_message, callable_bonds_account_selected_message

router = Router()
router.callback_query.filter(F.from_user.id.in_([user.telegram_id for user in settings.users]))


@router.callback_query(AccountCallbackFactory.filter())
async def callbacks_account(
        callback: CallbackQuery,
        callback_data: AccountCallbackFactory
):
    """
    Обработка команды привязки аккаунта брокера к отслеживанию индекса или отслеживанию действий по облигациям.
    Сохраняем переданный аккаунт в конфиг.
    :param callback:
    :param callback_data:
    """
    account_id = callback_data.account_id
    manager = PortfolioManager()
    account = [acc for acc in manager.get_user_accounts() if acc.id == account_id]

    ConfigLoader.update_broker_account(callback.from_user.id, account_id, account[0].name, callback_data.target)
    updated_settings = ConfigLoader.config
    if callback_data.target == "index_bindings":
        await tracking_index_setting_message(callback.message, manager.get_indices_list())
    elif callback_data.target == "bonds_account":
        await callable_bonds_account_selected_message(callback.message)

        user = [user for user in settings.users if user.telegram_id == callback.from_user.id][0]
        callable_bonds = manager.get_callable_bonds(account_id)
        reminder_state = user.schedule.enable_bond_reminder
        await account_callable_bonds_message(callback.message, callable_bonds, reminder_state, account_id)
    await callback.answer()


@router.callback_query(SetIndexCallbackFactory.filter())
async def callbacks_set_index(
        callback: CallbackQuery,
        callback_data: SetIndexCallbackFactory
):

    ConfigLoader.update_tracking_index(callback.from_user.id, callback_data.index)
    updated_settings = ConfigLoader.config
    await scheduler_setting_message(callback.message)
    await callback.answer()


@router.callback_query(ScheduleCallbackFactory.filter())
async def callbacks_schedule(
        callback: CallbackQuery,
        callback_data: ScheduleCallbackFactory
):

    ConfigLoader.update_schedule(callback.from_user.id, callback_data.frequency)
    updated_settings = ConfigLoader.config
    await welcome_user_answer(callback.message, settings.users[0].index_bindings)
    await callback.answer()


@router.callback_query(ActionsCallbackFactory.filter())
async def callbacks_actions(
            callback: CallbackQuery,
            callback_data: ActionsCallbackFactory,
            state: FSMContext
):
    """
    Ловим callback с командой действия и выполняем логику в зависимости от переданного действия.
    Поддерживаемые действия:
     * rebalance - выполнить балансировку, повторяя состав индекса к привязанному аккаунту.
     * check_bonds - выполнить проверку корпоративных действий на облигациях у указанного аккаунта.
     * relinked - изменить действующую связку между аккаунтом и индексом.
    :param callback:
    :param callback_data:
    :param state:
    :return:
    """
    user = [user for user in settings.users if user.telegram_id == callback.from_user.id][0]
    if callback_data.action == "rebalance":
        broker_account_id = user.index_bindings.broker_account_id

        manager = PortfolioManager(broker_account_id)
        portfolio = manager.get_portfolio()
        index_moex = manager.get_index_list(user.index_bindings.index_name)
        actions, new_balance = manager.get_action_for_rebalance(portfolio, index_moex)

        await portfolio_structure_message(callback.message, portfolio)
        await state.update_data(manager=manager)

        await actions_list_message(callback.message, actions)
        await callback.answer()
        await state.set_state(PortfolioRebalanceState.get_actions)

    if callback_data.action == "check_bonds":
        broker_account_for_bonds = check_bonds_account_exist(callback.from_user.id)
        if broker_account_for_bonds:
            broker_account_id = broker_account_for_bonds.broker_account_id
            manager = PortfolioManager(broker_account_id)
            callable_bonds = manager.get_callable_bonds()
            reminder_state = user.schedule.enable_bond_reminder
            await account_callable_bonds_message(callback.message, callable_bonds, reminder_state, broker_account_id)
        else:

            manager = PortfolioManager()
            accounts = manager.get_user_accounts()
            await callable_bonds_account_selecting_message(callback.message, accounts)
        await callback.answer()

    if callback_data.action == "relinked":
        manager = PortfolioManager()
        accounts = manager.get_user_accounts()
        await change_user_index_bindings_answer(callback.message, accounts)
        await callback.answer()


@router.callback_query(BalanceActionsCallbackFactory.filter())
async def callbacks_balance_actions(
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

@router.callback_query(ReminderCallbackFactory.filter())
async def callbacks_reminder(
        callback: CallbackQuery,
        callback_data: ReminderCallbackFactory
):
    """
    Ловим callback с командой о включении/выключении напоминания и обновляем конфигурацию.
    :param callback:
    :param callback_data:
    """

    ConfigLoader.change_bond_reminder_state(callback.from_user.id, callback_data.enabled)
    updated_settings = ConfigLoader.config
    await bonds_reminder_enabling_message(callback.message)
    await callback.answer()

@router.callback_query(SetCallableBondsAccountCallbackFactory.filter())
async def callbacks_set_callable_bonds_account(
        callback: CallbackQuery,
        callback_data: SetCallableBondsAccountCallbackFactory
):
    """
    Обработка команды запроса на необходимость изменения привязки аккаунта для отслеживания облигаций.
    Получаем все доступные аккаунты и предоставляем пользователю выбрать один.
    :param callback:
    :param callback_data:
    :return:
    """
    manager = PortfolioManager()
    accounts = manager.get_user_accounts()
    await callable_bonds_account_selecting_message(callback.message, accounts)
    await callback.answer()

