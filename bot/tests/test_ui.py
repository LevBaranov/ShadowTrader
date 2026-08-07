"""Тесты рендера бота: тексты и клавиатуры собираются из DTO API."""
import pytest

from bot import ui


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


def strategy(**overrides):
    data = {
        "id": "strategy-1",
        "brokerInfo": {
            "id": "broker-1",
            "name": "T-Bank",
            "account": {"id": "2000123456", "name": "Основной"},
        },
        "indexInfo": {"id": "index-1", "name": "IMOEX"},
        "brokersAccountId": "acc-pk-1",
        "accountDeleted": False,
    }
    data.update(overrides)
    return data


def button_texts(markup):
    return [button.text for row in markup.inline_keyboard for button in row]


class TestMainMenuKeyboard:

    def test_is_persistent_reply_keyboard(self):
        """Главное меню закреплено под полем ввода и не сворачивается."""
        markup = ui.main_menu_kb()

        assert markup.is_persistent is True
        assert markup.resize_keyboard is True

    def test_contains_all_sections(self):
        markup = ui.main_menu_kb()
        labels = [button.text for row in markup.keyboard for button in row]

        assert labels == [ui.BTN_STRATEGIES, ui.BTN_BONDS, ui.BTN_SETTINGS]


class TestAccountLabel:

    def test_uses_name(self):
        assert ui.account_label(account()) == "T-Bank / Основной"

    def test_falls_back_to_broker_account_id(self):
        assert ui.account_label(account(accountName="")) == "T-Bank / 2000123456"

    def test_marks_sandbox(self):
        assert "песочница" in ui.account_label(account(sandbox=True))


class TestAccountsKeyboard:

    def test_bonds_purpose_offers_every_account(self):
        accounts = [account(), account(id="acc-pk-2", hasStrategy=True)]

        texts = button_texts(ui.accounts_kb(accounts, purpose="bonds"))

        # Проверка облигаций не связана со стратегиями — доступны все счета.
        assert len([t for t in texts if t.startswith("T-Bank")]) == 2

    def test_strategy_purpose_hides_busy_accounts(self):
        accounts = [account(), account(id="acc-pk-2", hasStrategy=True)]

        texts = button_texts(ui.accounts_kb(accounts, purpose="strategy"))

        assert len([t for t in texts if t.startswith("T-Bank")]) == 1

    def test_has_refresh_button(self):
        assert "🔄 Обновить список" in button_texts(ui.accounts_kb([], purpose="bonds"))


class TestFormatBonds:

    @pytest.fixture
    def bonds(self):
        return [
            {
                "ticker": "RU000A105SK4",
                "name": "ОФЗ 26240",
                "quantity": 12,
                "events": [
                    {"type": "OFFER", "date": "2026-08-01"},
                    {"type": "CALL_OPTION", "date": "2026-09-15"},
                ],
            }
        ]

    def test_shows_event_type_and_date(self, bonds):
        text = ui.format_bonds(account(), bonds, "Облигации:")

        assert "RU000A105SK4 (ОФЗ 26240), 12 шт." in text
        assert "оферта: 01.08.2026" in text
        assert "колл-опцион: 15.09.2026" in text

    def test_shows_account(self, bonds):
        assert "T-Bank / Основной" in ui.format_bonds(account(), bonds, "Облигации:")

    def test_survives_unparsable_date(self):
        bonds = [{"ticker": "RU01", "events": [{"type": "OFFER", "date": "какая-то"}]}]

        assert "какая-то" in ui.format_bonds(account(), bonds, "Облигации:")


class TestBondsKeyboard:

    def test_offers_to_enable_monitoring(self):
        texts = button_texts(ui.bonds_kb(None, "acc-pk-1"))

        assert "🔔 Сообщить о событии" in texts

    def test_offers_to_disable_when_task_exists(self):
        texts = button_texts(ui.bonds_kb("task-1", "acc-pk-1"))

        assert "🔕 Не сообщать о событиях" in texts


class TestTaskLabel:

    def test_rebalance_names_strategy(self):
        task = {
            "id": "task-1",
            "type": "REBALANCE",
            "frequency": "WEEKLY",
            "params": {"strategy_id": "strategy-1"},
        }

        label = ui.task_label(task, [strategy()], [account()])

        assert "автобалансировка раз в неделю" in label
        assert "IMOEX" in label

    def test_bond_monitor_names_account(self):
        task = {
            "id": "task-2",
            "type": "BOND_EVENTS_MONITOR",
            "frequency": "WEEKLY",
            "params": {"brokers_account_id": "acc-pk-1"},
        }

        label = ui.task_label(task, [], [account()])

        assert "события по облигациям раз в неделю" in label
        assert "T-Bank / Основной" in label

    def test_unknown_target_is_omitted(self):
        task = {
            "id": "task-3",
            "type": "BOND_EVENTS_MONITOR",
            "frequency": "WEEKLY",
            "params": {"brokers_account_id": "gone"},
        }

        assert ui.task_label(task, [], []) == "события по облигациям раз в неделю"


class TestSettings:

    @pytest.fixture
    def profile(self):
        return {"email": "user@example.com", "pendingEmail": None, "telegramLinked": True}

    def test_lists_tasks_and_contacts(self, profile):
        task = {
            "id": "task-1",
            "type": "REBALANCE",
            "frequency": "MONTHLY",
            "params": {"strategy_id": "strategy-1"},
            "lastCheckedDate": "2026-07-01T10:00:00",
        }

        text = ui.format_settings(profile, [task], [strategy()], [account()])

        assert "user@example.com" in text
        assert "Telegram: привязан" in text
        assert "автобалансировка раз в месяц" in text
        assert "посл. запуск 2026-07-01" in text

    def test_shows_pending_email(self, profile):
        profile["pendingEmail"] = "new@example.com"

        assert "Ожидает подтверждения: new@example.com" in ui.format_settings(
            profile, [], [], []
        )

    def test_reports_empty_tasks(self, profile):
        assert "Задач по расписанию нет." in ui.format_settings(profile, [], [], [])

    def test_keyboard_covers_web_features(self):
        texts = button_texts(ui.settings_kb([], [], []))

        assert "🗓 Включить автобалансировку" in texts
        assert "🔔 Мониторинг облигаций" in texts
        assert "🔄 Обновить счета" in texts
        assert "🏦 Брокеры" in texts
        assert "✉️ Изменить почту" in texts
        assert "🔌 Отвязать Telegram" in texts

    def test_keyboard_offers_to_disable_each_task(self):
        tasks = [
            {"id": "t1", "type": "REBALANCE", "frequency": "WEEKLY",
             "params": {"strategy_id": "strategy-1"}},
            {"id": "t2", "type": "BOND_EVENTS_MONITOR", "frequency": "WEEKLY",
             "params": {"brokers_account_id": "acc-pk-1"}},
        ]

        texts = button_texts(ui.settings_kb(tasks, [strategy()], [account()]))

        assert len([t for t in texts if t.startswith("🔕 Отключить")]) == 2


class TestStrategyViewKeyboard:

    def test_offers_to_enable_schedule(self):
        texts = button_texts(ui.strategy_view_kb("strategy-1"))

        assert "🗓 Включить автобалансировку" in texts

    def test_shows_current_schedule(self):
        task = {"id": "task-1", "frequency": "QUARTERLY"}

        texts = button_texts(ui.strategy_view_kb("strategy-1", task))

        assert "🔕 Выключить автобалансировку (раз в квартал)" in texts


def broker(**overrides):
    data = {
        "id": "broker-1",
        "brokerName": "T-Bank",
        "sandbox": False,
        # Комиссия приходит долей: 0.003 = 0,3 %.
        "commission": "0.003",
    }
    data.update(overrides)
    return data


class TestBrokerLabel:
    """Комиссия — тариф брокера; в интерфейсе всегда проценты."""

    def test_shows_commission_as_percent(self):
        assert ui.broker_label(broker()) == "T-Bank, комиссия 0.3 %"

    def test_marks_sandbox(self):
        assert "песочница" in ui.broker_label(broker(sandbox=True))

    def test_survives_missing_commission(self):
        """Старый ответ бэкенда без комиссии не должен ронять рендер."""
        data = broker()
        del data["commission"]

        assert ui.broker_label(data) == "T-Bank"


class TestBrokersKeyboard:

    def test_offers_token_and_commission_per_broker(self):
        texts = button_texts(ui.brokers_kb([broker()]))

        assert any("Обновить токен" in text for text in texts)
        assert any("Комиссия" in text and "0.3 %" in text for text in texts)

    def test_offers_to_connect_when_empty(self):
        texts = button_texts(ui.brokers_kb([]))

        assert any("Подключить брокера" in text for text in texts)

    def test_skip_commission_keyboard(self):
        assert button_texts(ui.skip_commission_kb()) == ["⏭ Пропустить"]
