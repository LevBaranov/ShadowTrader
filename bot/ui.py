"""Рендер сообщений и клавиатур из DTO API (обычных dict'ов)."""
from datetime import date

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.percent import fraction_to_percent
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
)

BOND_EVENT_LABELS = {
    "OFFER": "оферта",
    "CALL_OPTION": "колл-опцион",
}

FREQUENCY_LABELS = {
    "WEEKLY": "раз в неделю",
    "MONTHLY": "раз в месяц",
    "QUARTERLY": "раз в квартал",
}

TASK_TYPE_LABELS = {
    "REBALANCE": "автобалансировка",
    "BOND_EVENTS_MONITOR": "события по облигациям",
}


def start_unlinked_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🆕 Зарегистрироваться", callback_data=MenuCb(section="signup"))
    builder.button(text="🔗 У меня есть аккаунт на вебе", callback_data=MenuCb(section="link"))
    builder.adjust(1)
    return builder.as_markup()


def link_kb(url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔗 Привязать аккаунт", url=url))
    builder.row(InlineKeyboardButton(
        text="✅ Я привязал — проверить",
        callback_data=MenuCb(section="check_link").pack(),
    ))
    return builder.as_markup()


# Тексты кнопок главного меню: постоянная reply-клавиатура шлёт их обычными
# сообщениями, по ним же матчатся хэндлеры в handlers.py.
BTN_STRATEGIES = "📊 Стратегии"
BTN_BONDS = "📄 Облигации"
BTN_SETTINGS = "⚙️ Настройки"


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Главное меню — постоянная клавиатура под полем ввода, доступна всегда."""
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text=BTN_STRATEGIES),
            KeyboardButton(text=BTN_BONDS),
            KeyboardButton(text=BTN_SETTINGS),
        ]],
        resize_keyboard=True,
        is_persistent=True,
    )


def strategy_label(strategy: dict) -> str:
    broker = strategy["brokerInfo"]
    label = (f"{broker['name']} / {broker['account']['name'] or broker['account']['id']}"
             f" → {strategy['indexInfo']['name']}")
    if strategy.get("accountDeleted"):
        label += " (счёт удалён)"
    return label


def account_label(account: dict) -> str:
    label = f"{account['brokerName']} / {account['accountName'] or account['accountId']}"
    if account.get("sandbox"):
        label += " (песочница)"
    return label


def strategies_kb(strategies: list[dict], action: str = "view") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for strategy in strategies:
        builder.button(
            text=strategy_label(strategy),
            callback_data=StrategyCb(action=action, id=strategy["id"]),
        )
    if action == "view":
        builder.button(text="➕ Новая стратегия", callback_data=MenuCb(section="new_strategy"))
    builder.button(text="↩️ В меню", callback_data=MenuCb(section="main"))
    builder.adjust(1)
    return builder.as_markup()


def strategy_view_kb(strategy_id: str, schedule_task: dict | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Выполнить балансировку", callback_data=StrategyCb(action="exec", id=strategy_id))

    if schedule_task:
        frequency = FREQUENCY_LABELS.get(schedule_task["frequency"], schedule_task["frequency"])
        builder.button(
            text=f"🔕 Выключить автобалансировку ({frequency})",
            callback_data=TaskCb(action="disable", id=schedule_task["id"]),
        )
    else:
        builder.button(
            text="🗓 Включить автобалансировку",
            callback_data=StrategyCb(action="schedule", id=strategy_id),
        )

    builder.button(text="🗑 Удалить стратегию", callback_data=StrategyCb(action="delete", id=strategy_id))
    builder.button(text="↩️ Назад", callback_data=MenuCb(section="strategies"))
    builder.adjust(1)
    return builder.as_markup()


def delete_confirm_kb(strategy_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Да, удалить", callback_data=StrategyCb(action="confirm_delete", id=strategy_id))
    builder.button(text="↩️ Назад", callback_data=StrategyCb(action="view", id=strategy_id))
    builder.adjust(1)
    return builder.as_markup()


def _broker_name(broker: dict) -> str:
    return broker["brokerName"] + (" (песочница)" if broker.get("sandbox") else "")


def broker_label(broker: dict) -> str:
    """Брокер строкой: имя, песочница и комиссия по тарифу."""
    name = _broker_name(broker)
    commission = broker.get("commission")

    if commission is None:
        return name

    return f"{name}, комиссия {fraction_to_percent(commission)} %"


def brokers_kb(brokers: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for broker in brokers:
        name = _broker_name(broker)
        builder.button(
            text=f"🔑 Обновить токен: {name}",
            callback_data=BrokerCb(action="retoken", id=broker["id"]),
        )
        builder.button(
            text=f"💰 Комиссия: {broker_label(broker)}",
            callback_data=BrokerCb(action="commission", id=broker["id"]),
        )
    builder.button(text="➕ Подключить брокера", callback_data=MenuCb(section="add_broker"))
    builder.button(text="↩️ Настройки", callback_data=MenuCb(section="settings"))
    builder.adjust(1)
    return builder.as_markup()


def skip_commission_kb() -> InlineKeyboardMarkup:
    """Комиссию можно не вводить — останется значение по умолчанию."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="⏭ Пропустить", callback_data=BrokerCb(action="skip_commission", id="0")
    )
    builder.adjust(1)
    return builder.as_markup()


def accounts_kb(accounts: list[dict], purpose: str) -> InlineKeyboardMarkup:
    """Клавиатура выбора счёта.

    purpose="strategy" — счета с уже созданной стратегией скрываются (на счёт
    допускается одна стратегия); purpose="bonds" — доступны все счета.
    """
    builder = InlineKeyboardBuilder()
    for account in accounts:
        if purpose == "strategy" and account.get("hasStrategy"):
            continue
        builder.button(
            text=account_label(account),
            callback_data=AccountCb(purpose=purpose, id=account["id"]),
        )
    builder.button(text="🔄 Обновить список", callback_data=RefreshAccountsCb(purpose=purpose))
    builder.button(text="↩️ В меню", callback_data=MenuCb(section="main"))
    builder.adjust(1)
    return builder.as_markup()


def indices_kb(indices: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index in indices:
        builder.button(text=index["indexName"], callback_data=IndexCb(id=index["id"]))
    builder.adjust(2)
    return builder.as_markup()


def freq_kb(strategy_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Раз в неделю", callback_data=FreqCb(frequency="WEEKLY", strategy_id=strategy_id))
    builder.button(text="Раз в месяц", callback_data=FreqCb(frequency="MONTHLY", strategy_id=strategy_id))
    builder.button(text="Раз в квартал", callback_data=FreqCb(frequency="QUARTERLY", strategy_id=strategy_id))
    builder.button(text="Пропустить", callback_data=FreqCb(frequency="SKIP", strategy_id=strategy_id))
    builder.adjust(1)
    return builder.as_markup()


def bonds_kb(monitor_task_id: str | None, brokers_account_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if monitor_task_id:
        builder.button(
            text="🔕 Не сообщать о событиях",
            callback_data=ReminderCb(enable=False, target_id=monitor_task_id),
        )
    else:
        builder.button(
            text="🔔 Сообщить о событии",
            callback_data=ReminderCb(enable=True, target_id=brokers_account_id),
        )
    builder.button(text="🔁 Другой счёт", callback_data=MenuCb(section="bonds"))
    builder.button(text="↩️ В меню", callback_data=MenuCb(section="main"))
    builder.adjust(1)
    return builder.as_markup()


def settings_kb(tasks: list[dict], strategies: list[dict], accounts: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for task in tasks:
        builder.button(
            text=f"🔕 Отключить: {task_label(task, strategies, accounts)}",
            callback_data=TaskCb(action="disable", id=task["id"]),
        )
    builder.button(text="🗓 Включить автобалансировку", callback_data=MenuCb(section="schedule"))
    builder.button(text="🔔 Мониторинг облигаций", callback_data=MenuCb(section="bonds"))
    builder.button(text="🔄 Обновить счета", callback_data=MenuCb(section="refresh_accounts"))
    builder.button(text="🏦 Брокеры", callback_data=MenuCb(section="brokers"))
    builder.button(text="✉️ Изменить почту", callback_data=MenuCb(section="change_email"))
    builder.button(text="🔌 Отвязать Telegram", callback_data=MenuCb(section="unlink_tg"))
    builder.button(text="↩️ В меню", callback_data=MenuCb(section="main"))
    builder.adjust(1)
    return builder.as_markup()


def unlink_confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔌 Да, отвязать", callback_data=MenuCb(section="unlink_tg_confirm"))
    builder.button(text="↩️ Отмена", callback_data=MenuCb(section="settings"))
    builder.adjust(1)
    return builder.as_markup()


def email_code_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔁 Отправить код ещё раз", callback_data=MenuCb(section="resend_email_code"))
    builder.button(text="✖️ Отменить смену почты", callback_data=MenuCb(section="cancel_email"))
    builder.adjust(1)
    return builder.as_markup()


def task_label(task: dict, strategies: list[dict], accounts: list[dict] = None) -> str:
    kind = TASK_TYPE_LABELS.get(task["type"], task["type"])
    frequency = FREQUENCY_LABELS.get(task["frequency"], task["frequency"])

    params = task.get("params") or {}
    strategy_id = params.get("strategy_id")
    account_id = params.get("brokers_account_id")

    target = ""
    if strategy_id:
        for strategy in strategies:
            if strategy["id"] == strategy_id:
                target = f" ({strategy_label(strategy)})"
                break
    elif account_id:
        for account in accounts or []:
            if account["id"] == account_id:
                target = f" ({account_label(account)})"
                break

    return f"{kind} {frequency}{target}"


def format_preview(strategy: dict, preview: dict) -> str:
    lines = [f"📊 {strategy_label(strategy)}", ""]

    positions = preview.get("portfolio") or []
    if positions:
        lines.append("Портфель (доля в портфеле → в индексе):")
        for position in positions:
            lines.append(
                f"• {position['ticker']}: {position['portfolioWeight']}% → {position['indexWeight']}%"
            )
        lines.append("")

    lines.append(f"Свободно: {preview['freeCash']:.2f} ₽")
    lines.append(f"Останется после балансировки: {preview['freeCashAfter']:.2f} ₽")
    lines.append("")

    actions = preview.get("actions") or []
    if actions:
        lines.append("План действий:")
        for action in actions:
            verb = "Купить" if action["type"] == "BUY" else "Продать"
            lines.append(f"• {verb} {action['ticker']} × {action['quantity']}")
    else:
        lines.append("Портфель сбалансирован, действий не требуется 👌")

    return "\n".join(lines)


def format_rebalance_result(result: dict) -> str:
    lines = []

    success = result.get("success") or []
    if success:
        lines.append("Выполнено ✅")
        for action in success:
            verb = "Купил" if action["type"] == "BUY" else "Продал"
            lines.append(f"• {verb} {action['ticker']} × {action['quantity']}")

    errors = result.get("errors") or []
    if errors:
        lines.append("")
        lines.append("Ошибки ⚠️")
        for error in errors:
            lines.append(f"• {error.get('ticker') or '?'}: {error.get('description')}")

    if not lines:
        lines.append("Действий не потребовалось 👌")

    return "\n".join(lines)


def _format_event_date(value: str) -> str:
    try:
        return date.fromisoformat(value).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return str(value)


def format_bonds(account: dict, bonds: list[dict], head: str) -> str:
    lines = [f"📄 {account_label(account)}", "", head]

    for bond in bonds:
        title = bond["ticker"]
        if bond.get("name"):
            title += f" ({bond['name']})"
        if bond.get("quantity"):
            title += f", {bond['quantity']} шт."
        lines.append(f"• {title}")

        for event in bond.get("events") or []:
            label = BOND_EVENT_LABELS.get(event["type"], event["type"])
            lines.append(f"    {label}: {_format_event_date(event['date'])}")

    return "\n".join(lines)


def format_settings(profile: dict, tasks: list[dict], strategies: list[dict], accounts: list[dict]) -> str:
    lines = ["⚙️ Настройки", ""]

    lines.append(f"Почта: {profile.get('email') or 'не задана (вход только через Telegram)'}")
    if profile.get("pendingEmail"):
        lines.append(f"Ожидает подтверждения: {profile['pendingEmail']}")
    lines.append(f"Telegram: {'привязан' if profile.get('telegramLinked') else 'не привязан'}")
    lines.append(f"Счетов у брокеров: {len(accounts)}")
    lines.append("")

    if tasks:
        lines.append("Активные задачи:")
        for task in tasks:
            checked = task.get("lastCheckedDate")
            checked_str = f", посл. запуск {checked[:10]}" if checked else ""
            lines.append(f"• {task_label(task, strategies, accounts)}{checked_str}")
    else:
        lines.append("Задач по расписанию нет.")

    return "\n".join(lines)
