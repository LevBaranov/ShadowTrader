"""Тесты экранов бота: какие запросы к API уходят и что видит пользователь.

API подменяется фейком — реальный бэкенд не нужен.
"""
import asyncio

import pytest

from bot import views


class FakeMessage:
    """Собирает ответы бота вместо отправки в Telegram."""

    def __init__(self):
        self.answers = []

    async def answer(self, text, reply_markup=None):
        self.answers.append((text, reply_markup))

    @property
    def last_text(self):
        return self.answers[-1][0]

    @property
    def last_buttons(self):
        markup = self.answers[-1][1]
        if markup is None:
            return []
        return [button.text for row in markup.inline_keyboard for button in row]


class FakeApi:
    def __init__(self, accounts=None, bonds=None, tasks=None, strategies=None, profile=None):
        self._accounts = accounts or []
        self._bonds = bonds or []
        self._tasks = tasks or []
        self._strategies = strategies or []
        self._profile = profile or {
            "email": "user@example.com", "pendingEmail": None, "telegramLinked": True
        }
        self.calls = []

    async def get_accounts(self, telegram_id):
        self.calls.append("get_accounts")
        return self._accounts

    async def get_bond_events(self, telegram_id, brokers_account_id):
        self.calls.append(f"get_bond_events:{brokers_account_id}")
        return self._bonds

    async def list_tasks(self, telegram_id):
        self.calls.append("list_tasks")
        return self._tasks

    async def get_strategies(self, telegram_id):
        self.calls.append("get_strategies")
        return self._strategies

    async def get_profile(self, telegram_id):
        self.calls.append("get_profile")
        return self._profile

    async def get_brokers(self, telegram_id):
        self.calls.append("get_brokers")
        return []


TELEGRAM_ID = 123456789


def account(**overrides):
    data = {
        "id": "acc-pk-1",
        "accountId": "2000123456",
        "accountName": "Основной",
        "brokerId": "broker-1",
        "brokerName": "T-Bank",
        "sandbox": False,
        "hasStrategy": False,
    }
    data.update(overrides)
    return data


BOND = {
    "ticker": "RU000A105SK4",
    "name": "ОФЗ 26240",
    "quantity": 3,
    "events": [{"type": "OFFER", "date": "2026-08-01"}],
}


@pytest.fixture
def message():
    return FakeMessage()


class TestShowAccounts:

    def test_bonds_purpose_asks_to_choose_account(self, message):
        api = FakeApi(accounts=[account()])

        asyncio.run(views.show_accounts(message, api, TELEGRAM_ID, purpose="bonds"))

        assert "Выбери счёт, на котором проверить облигации" in message.last_text
        assert "T-Bank / Основной" in message.last_buttons

    def test_bonds_purpose_allows_account_with_strategy(self, message):
        api = FakeApi(accounts=[account(hasStrategy=True)])

        asyncio.run(views.show_accounts(message, api, TELEGRAM_ID, purpose="bonds"))

        assert "T-Bank / Основной" in message.last_buttons

    def test_reports_no_accounts(self, message):
        api = FakeApi(accounts=[])

        asyncio.run(views.show_accounts(message, api, TELEGRAM_ID, purpose="bonds"))

        assert "не нашлось счетов" in message.last_text

    def test_strategy_purpose_reports_all_busy(self, message):
        api = FakeApi(accounts=[account(hasStrategy=True)])

        asyncio.run(views.show_accounts(message, api, TELEGRAM_ID, purpose="strategy"))

        assert "На всех счетах уже есть стратегии" in message.last_text

    def test_reuses_given_accounts(self, message):
        api = FakeApi(accounts=[account()])

        asyncio.run(views.show_accounts(
            message, api, TELEGRAM_ID, purpose="bonds", accounts=[account()]
        ))

        assert "get_accounts" not in api.calls


class TestShowBonds:

    def test_shows_events_with_dates(self, message):
        api = FakeApi(accounts=[account()], bonds=[BOND])

        asyncio.run(views.show_bonds(message, api, TELEGRAM_ID, "acc-pk-1"))

        assert "RU000A105SK4" in message.last_text
        assert "оферта: 01.08.2026" in message.last_text

    def test_offers_to_report_event(self, message):
        api = FakeApi(accounts=[account()], bonds=[BOND])

        asyncio.run(views.show_bonds(message, api, TELEGRAM_ID, "acc-pk-1"))

        assert "🔔 Сообщить о событии" in message.last_buttons

    def test_offers_to_disable_existing_monitor(self, message):
        task = {
            "id": "task-1",
            "type": "BOND_EVENTS_MONITOR",
            "frequency": "WEEKLY",
            "params": {"brokers_account_id": "acc-pk-1"},
        }
        api = FakeApi(accounts=[account()], bonds=[BOND], tasks=[task])

        asyncio.run(views.show_bonds(message, api, TELEGRAM_ID, "acc-pk-1"))

        assert "🔕 Не сообщать о событиях" in message.last_buttons

    def test_monitor_of_another_account_is_ignored(self, message):
        task = {
            "id": "task-1",
            "type": "BOND_EVENTS_MONITOR",
            "frequency": "WEEKLY",
            "params": {"brokers_account_id": "acc-pk-2"},
        }
        api = FakeApi(accounts=[account()], bonds=[BOND], tasks=[task])

        asyncio.run(views.show_bonds(message, api, TELEGRAM_ID, "acc-pk-1"))

        assert "🔔 Сообщить о событии" in message.last_buttons

    def test_empty_result_still_offers_monitoring(self, message):
        api = FakeApi(accounts=[account()], bonds=[])

        asyncio.run(views.show_bonds(message, api, TELEGRAM_ID, "acc-pk-1"))

        assert "нет облигаций с предстоящей офертой" in message.last_text
        assert "🔔 Сообщить о событии" in message.last_buttons

    def test_unknown_account_returns_to_choice(self, message):
        api = FakeApi(accounts=[account()], bonds=[BOND])

        asyncio.run(views.show_bonds(message, api, TELEGRAM_ID, "gone"))

        assert "Выбери счёт" in message.last_text
        assert "get_bond_events:gone" not in api.calls


class TestFindTask:

    def test_matches_type_and_params(self):
        tasks = [
            {"type": "REBALANCE", "params": {"strategy_id": "s-1"}},
            {"type": "BOND_EVENTS_MONITOR", "params": {"brokers_account_id": "a-1"}},
        ]

        found = views.find_task(tasks, "BOND_EVENTS_MONITOR", brokers_account_id="a-1")

        assert found["type"] == "BOND_EVENTS_MONITOR"

    def test_returns_none_when_params_differ(self):
        tasks = [{"type": "REBALANCE", "params": {"strategy_id": "s-1"}}]

        assert views.find_task(tasks, "REBALANCE", strategy_id="s-2") is None

    def test_handles_task_without_params(self):
        tasks = [{"type": "REBALANCE", "params": None}]

        assert views.find_task(tasks, "REBALANCE", strategy_id="s-1") is None


class TestShowSettings:

    def test_shows_profile_and_tasks(self, message):
        task = {
            "id": "task-1",
            "type": "BOND_EVENTS_MONITOR",
            "frequency": "WEEKLY",
            "params": {"brokers_account_id": "acc-pk-1"},
        }
        api = FakeApi(accounts=[account()], tasks=[task])

        asyncio.run(views.show_settings(message, api, TELEGRAM_ID))

        assert "user@example.com" in message.last_text
        assert "события по облигациям раз в неделю" in message.last_text
        assert "🔕 Отключить: события по облигациям раз в неделю (T-Bank / Основной)" in (
            message.last_buttons
        )
