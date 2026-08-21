"""Общие «экраны» бота: используются и командами, и колбэками."""
from aiogram.types import Message

from bot import texts, ui
from bot.api_client import ShadowTraderApi

BOND_MONITOR_TASK = "BOND_EVENTS_MONITOR"
REBALANCE_TASK = "REBALANCE"


def find_task(tasks: list[dict], task_type: str, **params) -> dict | None:
    """Активная задача пользователя нужного типа с совпадающими params."""
    for task in tasks:
        if task["type"] != task_type:
            continue
        task_params = task.get("params") or {}
        if all(task_params.get(key) == value for key, value in params.items()):
            return task
    return None


async def show_start(message: Message, api: ShadowTraderApi, telegram_id: int) -> None:
    if await api.is_linked(telegram_id):
        await message.answer(texts.WELCOME_LINKED, reply_markup=ui.main_menu_kb())
    else:
        await message.answer(texts.WELCOME_UNLINKED, reply_markup=ui.start_unlinked_kb())


async def show_main_menu(message: Message) -> None:
    await message.answer(texts.WELCOME_LINKED, reply_markup=ui.main_menu_kb())


async def show_link_offer(message: Message, api: ShadowTraderApi, telegram_id: int, web_app_url: str) -> None:
    link_request = await api.create_link_request(telegram_id)
    url = f"{web_app_url.rstrip('/')}/link-telegram?code={link_request['code']}"
    await message.answer(texts.LINK_OFFER, reply_markup=ui.link_kb(url))


async def show_strategies(message: Message, api: ShadowTraderApi, telegram_id: int) -> None:
    strategies = await api.get_strategies(telegram_id)
    if strategies:
        await message.answer(texts.STRATEGIES_LIST, reply_markup=ui.strategies_kb(strategies))
    else:
        await message.answer(texts.STRATEGIES_EMPTY, reply_markup=ui.strategies_kb([]))


async def show_accounts(
        message: Message,
        api: ShadowTraderApi,
        telegram_id: int,
        purpose: str,
        accounts: list[dict] | None = None,
) -> None:
    """Выбор счёта: для новой стратегии (purpose="strategy") или облигаций ("bonds")."""
    if accounts is None:
        accounts = await api.get_accounts(telegram_id)

    if not accounts:
        await message.answer(texts.ACCOUNTS_EMPTY, reply_markup=ui.accounts_kb([], purpose))
        return

    if purpose == "strategy" and all(account.get("hasStrategy") for account in accounts):
        await message.answer(texts.ACCOUNTS_ALL_BUSY, reply_markup=ui.accounts_kb(accounts, purpose))
        return

    text = texts.CHOOSE_ACCOUNT if purpose == "strategy" else texts.CHOOSE_ACCOUNT_BONDS
    await message.answer(text, reply_markup=ui.accounts_kb(accounts, purpose))


async def show_bonds(
        message: Message, api: ShadowTraderApi, telegram_id: int, brokers_account_id: str
) -> None:
    """Облигации выбранного счёта: события с датами + переключатель уведомлений."""
    accounts = await api.get_accounts(telegram_id)
    account = next((a for a in accounts if a["id"] == brokers_account_id), None)
    if account is None:
        await show_accounts(message, api, telegram_id, purpose="bonds", accounts=accounts)
        return

    bonds = await api.get_bond_events(telegram_id, brokers_account_id)

    tasks = await api.list_tasks(telegram_id)
    monitor_task = find_task(tasks, BOND_MONITOR_TASK, brokers_account_id=brokers_account_id)

    text = (
        ui.format_bonds(account, bonds, texts.BONDS_HEAD)
        if bonds
        else f"📄 {ui.account_label(account)}\n\n{texts.BONDS_EMPTY}"
    )

    await message.answer(
        text,
        reply_markup=ui.bonds_kb(
            monitor_task["id"] if monitor_task else None,
            brokers_account_id,
        ),
    )


async def show_settings(message: Message, api: ShadowTraderApi, telegram_id: int) -> None:
    profile = await api.get_profile(telegram_id)
    tasks = await api.list_tasks(telegram_id)
    strategies = await api.get_strategies(telegram_id)
    accounts = await api.get_accounts(telegram_id)

    await message.answer(
        ui.format_settings(profile, tasks, strategies, accounts),
        reply_markup=ui.settings_kb(tasks, strategies, accounts),
    )


async def show_brokers(message: Message, api: ShadowTraderApi, telegram_id: int) -> None:
    brokers = await api.get_brokers(telegram_id)
    if brokers:
        await message.answer(texts.BROKERS_LIST, reply_markup=ui.brokers_kb(brokers))
    else:
        await message.answer(texts.NO_BROKERS, reply_markup=ui.brokers_kb([]))
