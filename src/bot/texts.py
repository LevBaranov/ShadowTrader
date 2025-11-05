welcome_head = "Приветственный привет!\n"
welcome_guest = """Необходимо настроить связку счёт брокера и индекс МБ. Выберете счёт брокера для привязки
Кол-во счетов обнаружено: $accounts_count
"""
welcome_user = """У вас обнаружена действующая связка: 
Портфель: $account_name и Индекс МБ: $index_name
"""
action = "Действие: $type, Акция: $ticker, Кол-во: $count"
free_cash = "Текущие свободные средства: $cash \n"
position = "$ticker: $balance шт"
error_text = "При выполнении действия с $ticker ошибка: $error"
success = "Успешно:\n"
errors = "Ошибки:\n"
set_scheduler = "Выберите как часто выполнять синхронизацию:"
set_tracking_index = "Выберите, что хотите отслеживать:"
user_settings_text_template = """Пользователь: $telegram_id
Аккаунт брокера: $broker_account_name
Индекс Мосбиржи: $index_name

Расписание настроено: $rebalance_frequency
Последняя балансировка была: $last_run
"""
user_settings_text_template_with_bonds = """
Облигации проверял на аккаунте: $bonds_broker_account_name
Последний раз проверял состояние облигаций: $bonds_reminder_last_run 
"""
callable_bonds_head_template = "Тикер - Название - Дата оферты"
callable_bonds_text_template = "$ticker - $name - $offer_date "
bonds_reminder_template = "Напоминание о событиях по облигациям включено"
callable_bonds_account_selecting_template = """Выберете счёт брокера на котором необходимо отслеживать облигации.
Кол-во счетов обнаружено: $accounts_count
"""
callable_bonds_account_selected_template = "Счёт брокера для отслеживания облигации обновлён."
