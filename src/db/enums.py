from enum import Enum

class TaskType(str, Enum):
    BOND_EVENTS_MONITOR = "Проверка событий по облигациям"
    REBALANCE = "Балансировка портфеля по стратегии"
    INDEX_SYNC = "Синхронизация составов индексов"
    MOEX_BONDS_SYNC = "Синхронизация справочника облигаций MOEX"
    MOEX_BONDS_OFFER_DATE_SYNC = "Синхронизация дат подачи заявок на оферту"
    NOTIFY_START_OFFER_DATE = "Уведомление о дате подачи заявок на оферту"


class AuthProvider(str, Enum):
    EMAIL = "EMAIL"
    TELEGRAM = "TELEGRAM"
