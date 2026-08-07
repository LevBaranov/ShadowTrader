import re

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from bot import texts, ui, views
from bot.api_client import ShadowTraderApi, ApiError
from bot.percent import fraction_to_percent, parse_percent
from bot.utils import (
    MenuCb,
    StrategyCb,
    BrokerCb,
    RefreshAccountsCb,
    AccountCb,
    IndexCb,
    FreqCb,
    ReminderCb,
    TaskCb,
    NewStrategyState,
    BrokerCommissionState,
    EmailChangeState,
)

router = Router()

# Пока поддерживается один брокер; список нужен, чтобы при добавлении второго
# здесь появился выбор, а не правка по всему файлу.
BROKER_NAME = "T-Bank"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 6


@router.callback_query(MenuCb.filter())
async def on_menu(
        callback: CallbackQuery,
        callback_data: MenuCb,
        api: ShadowTraderApi,
        state: FSMContext,
        web_app_url: str,
):
    telegram_id = callback.from_user.id
    message = callback.message
    section = callback_data.section

    if section == "main":
        await state.clear()
        await views.show_main_menu(message)

    elif section == "strategies":
        await views.show_strategies(message, api, telegram_id)

    elif section == "bonds":
        await views.show_accounts(message, api, telegram_id, purpose="bonds")

    elif section == "settings":
        await views.show_settings(message, api, telegram_id)

    elif section == "signup":
        try:
            await api.register_telegram_user(telegram_id)
        except ApiError as error:
            # Гонка двойного клика: аккаунт уже создан — продолжаем как ни в чём не бывало.
            if error.detail != "telegram_already_linked":
                raise
        await message.answer(texts.REGISTERED)
        await views.show_main_menu(message)

    elif section == "link":
        await views.show_link_offer(message, api, telegram_id, web_app_url)

    elif section == "check_link":
        if await api.is_linked(telegram_id):
            await views.show_main_menu(message)
        else:
            await callback.answer(texts.LINK_NOT_CONFIRMED, show_alert=True)
            return

    elif section == "new_strategy":
        accounts = await api.get_accounts(telegram_id)
        if accounts:
            await views.show_accounts(
                message, api, telegram_id, purpose="strategy", accounts=accounts
            )
        else:
            # Счетов нет вообще — значит и брокера нет, начинаем с токена.
            await message.answer(texts.NO_BROKERS)
            await _ask_broker_token(message, state, back_to="strategy")

    elif section == "brokers":
        await views.show_brokers(message, api, telegram_id)

    elif section == "add_broker":
        # Брокера подключают из настроек — туда же и возвращаемся.
        await _ask_broker_token(message, state, back_to="settings")

    elif section == "refresh_accounts":
        await api.refresh_accounts(telegram_id)
        await message.answer(texts.ACCOUNTS_REFRESHED)
        await views.show_settings(message, api, telegram_id)

    elif section == "schedule":
        strategies = await api.get_strategies(telegram_id)
        if strategies:
            await message.answer(
                texts.STRATEGIES_LIST,
                reply_markup=ui.strategies_kb(strategies, action="schedule"),
            )
        else:
            await message.answer(texts.STRATEGIES_EMPTY, reply_markup=ui.strategies_kb([]))

    elif section == "change_email":
        await state.set_state(EmailChangeState.waiting_email)
        await message.answer(texts.ASK_NEW_EMAIL)

    elif section == "resend_email_code":
        try:
            pending = await api.resend_email_code(telegram_id)
        except ApiError as error:
            await message.answer(_email_error_text(error))
        else:
            await state.set_state(EmailChangeState.waiting_code)
            await message.answer(
                texts.ASK_EMAIL_CODE.format(email=pending["pendingEmail"]),
                reply_markup=ui.email_code_kb(),
            )

    elif section == "cancel_email":
        try:
            await api.cancel_email_change(telegram_id)
        except ApiError as error:
            if error.detail != "no_pending_email":
                raise
        await state.clear()
        await message.answer(texts.EMAIL_CHANGE_CANCELLED)
        await views.show_settings(message, api, telegram_id)

    elif section == "unlink_tg":
        await message.answer(texts.UNLINK_TG_CONFIRM, reply_markup=ui.unlink_confirm_kb())

    elif section == "unlink_tg_confirm":
        try:
            await api.unlink_telegram(telegram_id)
        except ApiError as error:
            if error.detail == "last_login_method":
                await message.answer(texts.UNLINK_TG_LAST_METHOD)
                await callback.answer()
                return
            raise
        await state.clear()
        # Главное меню закреплено reply-клавиатурой — у отвязанного пользователя
        # ей делать нечего, убираем.
        await message.answer(texts.UNLINK_TG_DONE, reply_markup=ReplyKeyboardRemove())

    await callback.answer()


async def _ask_broker_token(message: Message, state: FSMContext, back_to: str) -> None:
    """Запросить токен брокера, запомнив, куда вернуть пользователя после сохранения."""
    await state.set_state(NewStrategyState.waiting_broker_token)
    await state.update_data(broker_token_back_to=back_to)
    await message.answer(texts.ASK_BROKER_TOKEN)


@router.message(NewStrategyState.waiting_broker_token)
async def on_broker_token(message: Message, api: ShadowTraderApi, state: FSMContext):
    token = (message.text or "").strip()
    telegram_id = message.from_user.id

    # Сообщение с токеном удаляем сразу — секрету нечего делать в истории чата.
    try:
        await message.delete()
    except Exception:
        pass

    try:
        await api.save_broker(telegram_id, BROKER_NAME, token)
    except ApiError as error:
        if error.status_code == 422:
            await message.answer(texts.BROKER_TOKEN_INVALID)
            return
        raise

    await message.answer(texts.BROKER_SAVED)

    # Токен сохранён, брокер уже рабочий — комиссия отдельным шагом, её можно
    # пропустить и поправить позже в настройках.
    await state.set_state(NewStrategyState.waiting_broker_commission)
    await message.answer(
        texts.ASK_BROKER_COMMISSION, reply_markup=ui.skip_commission_kb()
    )


async def _finish_broker_setup(
        message: Message, api: ShadowTraderApi, state: FSMContext, telegram_id: int
) -> None:
    """Куда вернуть пользователя после подключения брокера."""
    data = await state.get_data()
    back_to = data.get("broker_token_back_to", "strategy")
    await state.clear()

    if back_to == "settings":
        await views.show_settings(message, api, telegram_id)
    else:
        # Счета нового брокера подтянутся при запросе списка.
        await views.show_accounts(message, api, telegram_id, purpose="strategy")


@router.message(NewStrategyState.waiting_broker_commission)
async def on_broker_commission(message: Message, api: ShadowTraderApi, state: FSMContext):
    commission = parse_percent(message.text)
    if commission is None:
        await message.answer(
            texts.BROKER_COMMISSION_INVALID, reply_markup=ui.skip_commission_kb()
        )
        return

    telegram_id = message.from_user.id
    broker = await _save_commission(api, telegram_id, commission)

    await message.answer(
        texts.BROKER_COMMISSION_SAVED.format(
            percent=fraction_to_percent(broker["commission"])
        )
    )
    await _finish_broker_setup(message, api, state, telegram_id)


async def _save_commission(api: ShadowTraderApi, telegram_id: int, commission) -> dict:
    """Записать комиссию единственному брокеру пользователя (пока брокер один)."""
    brokers = await api.get_brokers(telegram_id)
    broker = next(
        (item for item in brokers if item["brokerName"] == BROKER_NAME), None
    )
    if broker is None:
        raise ApiError(404, "broker_not_found")

    return await api.update_broker(telegram_id, broker["id"], commission)


@router.message(BrokerCommissionState.waiting_commission)
async def on_broker_commission_change(
        message: Message, api: ShadowTraderApi, state: FSMContext
):
    """Правка комиссии у подключённого брокера — токен не нужен."""
    commission = parse_percent(message.text)
    if commission is None:
        await message.answer(texts.BROKER_COMMISSION_INVALID)
        return

    telegram_id = message.from_user.id
    data = await state.get_data()
    broker_id = data.get("commission_broker_id")
    await state.clear()

    broker = await api.update_broker(telegram_id, broker_id, commission)

    await message.answer(
        texts.BROKER_COMMISSION_SAVED.format(
            percent=fraction_to_percent(broker["commission"])
        )
    )
    await views.show_brokers(message, api, telegram_id)


@router.callback_query(StrategyCb.filter())
async def on_strategy(
        callback: CallbackQuery,
        callback_data: StrategyCb,
        api: ShadowTraderApi,
):
    telegram_id = callback.from_user.id
    message = callback.message
    strategy_id = callback_data.id
    action = callback_data.action

    if action == "view":
        strategies = await api.get_strategies(telegram_id)
        strategy = next((s for s in strategies if s["id"] == strategy_id), None)
        if strategy is None:
            await views.show_strategies(message, api, telegram_id)
            await callback.answer()
            return

        tasks = await api.list_tasks(telegram_id)
        schedule_task = views.find_task(
            tasks, views.REBALANCE_TASK, strategy_id=strategy_id
        )

        await callback.answer("Считаю план балансировки…")
        try:
            preview = await api.get_rebalance_preview(telegram_id, strategy_id)
        except ApiError as error:
            if error.detail == "account_deleted":
                await message.answer(
                    "Счёт этой стратегии удалён у брокера — операции недоступны.",
                    reply_markup=ui.strategy_view_kb(strategy_id, schedule_task),
                )
                return
            raise
        await message.answer(
            ui.format_preview(strategy, preview),
            reply_markup=ui.strategy_view_kb(strategy_id, schedule_task),
        )
        return

    if action == "exec":
        await callback.answer("Выполняю…")
        result = await api.execute_rebalance(telegram_id, strategy_id)
        await message.answer(ui.format_rebalance_result(result), reply_markup=ui.main_menu_kb())
        return

    if action == "delete":
        await message.answer(texts.DELETE_CONFIRM, reply_markup=ui.delete_confirm_kb(strategy_id))

    elif action == "confirm_delete":
        await api.delete_strategy(telegram_id, strategy_id)
        await message.answer(texts.DELETED)
        await views.show_strategies(message, api, telegram_id)

    elif action == "schedule":
        await message.answer("Как часто балансировать?", reply_markup=ui.freq_kb(strategy_id))

    await callback.answer()


@router.callback_query(BrokerCb.filter())
async def on_broker(
        callback: CallbackQuery,
        callback_data: BrokerCb,
        api: ShadowTraderApi,
        state: FSMContext,
):
    if callback_data.action == "retoken":
        # Токен перезаписывается тем же PUT /brokers по имени брокера.
        await _ask_broker_token(callback.message, state, back_to="settings")

    elif callback_data.action == "commission":
        await state.set_state(BrokerCommissionState.waiting_commission)
        await state.update_data(commission_broker_id=callback_data.id)
        await callback.message.answer(texts.ASK_BROKER_COMMISSION)

    elif callback_data.action == "skip_commission":
        # Комиссию не вводим — остаётся значение по умолчанию из БД.
        await _finish_broker_setup(
            callback.message, api, state, callback.from_user.id
        )

    await callback.answer()


@router.callback_query(RefreshAccountsCb.filter())
async def on_refresh_accounts(
        callback: CallbackQuery, callback_data: RefreshAccountsCb, api: ShadowTraderApi
):
    accounts = await api.refresh_accounts(callback.from_user.id)
    await views.show_accounts(
        callback.message,
        api,
        callback.from_user.id,
        purpose=callback_data.purpose,
        accounts=accounts,
    )
    await callback.answer()


@router.callback_query(AccountCb.filter())
async def on_account(
        callback: CallbackQuery,
        callback_data: AccountCb,
        api: ShadowTraderApi,
        state: FSMContext,
):
    telegram_id = callback.from_user.id

    if callback_data.purpose == "bonds":
        await callback.answer("Смотрю облигации…")
        await views.show_bonds(callback.message, api, telegram_id, callback_data.id)
        return

    await state.update_data(brokers_account_id=callback_data.id)
    indices = await api.get_indices(telegram_id)
    await callback.message.answer(texts.CHOOSE_INDEX, reply_markup=ui.indices_kb(indices))
    await callback.answer()


@router.callback_query(IndexCb.filter())
async def on_index(
        callback: CallbackQuery,
        callback_data: IndexCb,
        api: ShadowTraderApi,
        state: FSMContext,
):
    data = await state.get_data()
    brokers_account_id = data.get("brokers_account_id")
    if not brokers_account_id:
        await callback.answer("Счёт не выбран — начни заново.", show_alert=True)
        return

    strategy = await api.create_strategy(
        callback.from_user.id, brokers_account_id, callback_data.id
    )
    await state.clear()

    await callback.message.answer(
        texts.STRATEGY_CREATED, reply_markup=ui.freq_kb(strategy["id"])
    )
    await callback.answer()


@router.callback_query(FreqCb.filter())
async def on_frequency(callback: CallbackQuery, callback_data: FreqCb, api: ShadowTraderApi):
    message = callback.message

    if callback_data.frequency != "SKIP":
        try:
            await api.create_task(
                callback.from_user.id,
                views.REBALANCE_TASK,
                callback_data.frequency,
                {"strategy_id": callback_data.strategy_id},
            )
            await message.answer(texts.TASK_CREATED)
        except ApiError as error:
            if error.detail != "task_already_exists":
                raise
            await message.answer("Автобалансировка по этой стратегии уже включена.")

    await views.show_main_menu(message)
    await callback.answer()


@router.callback_query(ReminderCb.filter())
async def on_reminder(callback: CallbackQuery, callback_data: ReminderCb, api: ShadowTraderApi):
    telegram_id = callback.from_user.id
    message = callback.message

    if callback_data.enable:
        try:
            await api.create_task(
                telegram_id,
                views.BOND_MONITOR_TASK,
                "WEEKLY",
                {"brokers_account_id": callback_data.target_id},
            )
        except ApiError as error:
            if error.detail != "task_already_exists":
                raise
        await message.answer(texts.REMINDER_ENABLED)
        await views.show_bonds(message, api, telegram_id, callback_data.target_id)
    else:
        await api.delete_task(telegram_id, callback_data.target_id)
        await message.answer(texts.REMINDER_DISABLED)

    await callback.answer()


@router.callback_query(TaskCb.filter())
async def on_task(callback: CallbackQuery, callback_data: TaskCb, api: ShadowTraderApi):
    if callback_data.action == "disable":
        try:
            await api.delete_task(callback.from_user.id, callback_data.id)
        except ApiError as error:
            if error.detail != "task_not_found":
                raise
        await callback.message.answer(texts.TASK_DISABLED)
        await views.show_settings(callback.message, api, callback.from_user.id)
    await callback.answer()


# --- смена почты ---

def _email_error_text(error: ApiError) -> str:
    """Машинный код ошибки бэкенда → текст для пользователя."""
    return {
        "email_already_registered": texts.EMAIL_TAKEN,
        "email_unchanged": texts.EMAIL_UNCHANGED,
        "invalid_code": texts.EMAIL_CODE_INVALID,
        "code_expired": texts.EMAIL_CODE_EXPIRED,
        "too_many_attempts": texts.EMAIL_CODE_TOO_MANY,
        "resend_cooldown": texts.EMAIL_RESEND_COOLDOWN,
        "email_send_failed": texts.EMAIL_SEND_FAILED,
    }.get(error.detail, texts.GENERIC_ERROR)


async def _request_email_change(
        message: Message,
        api: ShadowTraderApi,
        state: FSMContext,
        email: str,
        password: str | None = None,
) -> None:
    telegram_id = message.from_user.id

    try:
        pending = await api.request_email_change(telegram_id, email, password)
    except ApiError as error:
        if error.detail == "password_required":
            # Входа по почте ещё нет — без пароля новая почта бесполезна.
            await state.update_data(new_email=email)
            await state.set_state(EmailChangeState.waiting_password)
            await message.answer(texts.ASK_EMAIL_PASSWORD)
            return
        if error.status_code == 422:
            await message.answer(texts.EMAIL_INVALID)
            return

        await state.clear()
        await message.answer(_email_error_text(error))
        return

    await state.set_state(EmailChangeState.waiting_code)
    await message.answer(
        texts.ASK_EMAIL_CODE.format(email=pending["pendingEmail"]),
        reply_markup=ui.email_code_kb(),
    )


@router.message(EmailChangeState.waiting_email)
async def on_new_email(message: Message, api: ShadowTraderApi, state: FSMContext):
    email = (message.text or "").strip().lower()

    if not EMAIL_RE.match(email):
        await message.answer(texts.EMAIL_INVALID)
        return

    await _request_email_change(message, api, state, email)


@router.message(EmailChangeState.waiting_password)
async def on_email_password(message: Message, api: ShadowTraderApi, state: FSMContext):
    password = (message.text or "").strip()

    # Пароль в истории чата не оставляем.
    try:
        await message.delete()
    except Exception:
        pass

    if len(password) < MIN_PASSWORD_LENGTH:
        await message.answer(texts.EMAIL_PASSWORD_TOO_SHORT)
        return

    data = await state.get_data()
    email = data.get("new_email")
    if not email:
        await state.set_state(EmailChangeState.waiting_email)
        await message.answer(texts.ASK_NEW_EMAIL)
        return

    await _request_email_change(message, api, state, email, password)


@router.message(EmailChangeState.waiting_code)
async def on_email_code(message: Message, api: ShadowTraderApi, state: FSMContext):
    code = (message.text or "").strip()
    telegram_id = message.from_user.id

    try:
        profile = await api.confirm_email_change(telegram_id, code)
    except ApiError as error:
        await message.answer(_email_error_text(error), reply_markup=ui.email_code_kb())
        return

    await state.clear()
    await message.answer(texts.EMAIL_CHANGED.format(email=profile["email"]))
    await views.show_settings(message, api, telegram_id)
