"""Тексты отчётов планировщика для уведомлений пользователю."""

REPORT_HEAD = "Я тут немного «пошуршал», пока ты не видел.\n"


def rebalance_report(success_actions, error_actions) -> str:
    lines = [REPORT_HEAD, "Успешно:"]
    for action in success_actions:
        ticker = action.share.ticker if action.share else "?"
        lines.append(f"Действие: {action.type}, Акция: {ticker}, Кол-во: {action.quantity}")

    if error_actions:
        lines.append("Ошибки:")
        for error in error_actions:
            action = getattr(error, "data", None)
            ticker = action.share.ticker if action is not None and getattr(action, "share", None) else "?"
            lines.append(f"При выполнении действия с {ticker} ошибка: {error.description}")

    return "\n".join(lines)


BOND_EVENT_LABELS = {
    "OFFER": "оферта",
    "CALL_OPTION": "колл-опцион",
}


def bonds_report(bonds_with_events) -> str:
    """Отчёт о близких событиях по облигациям.

    bonds_with_events — пары (облигация, попавшие в горизонт события).
    """
    lines = [REPORT_HEAD, "Скоро события по облигациям на счёте:"]
    for bond, events in bonds_with_events:
        title = f"{bond.ticker}"
        if getattr(bond, "short_name", None):
            title += f" ({bond.short_name})"

        for event in events:
            label = BOND_EVENT_LABELS.get(event.type.name, event.type.value)
            lines.append(f"{title} — {label} {event.date:%d.%m.%Y}")

    return "\n".join(lines)
