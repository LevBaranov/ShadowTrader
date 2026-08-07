from enum import Enum

class TaskType(str, Enum):
    BOND_EVENTS_MONITOR = "Проверка событий по облигациям"
    REBALANCE = "Балансировка портфеля по стратегии"


class AuthProvider(str, Enum):
    EMAIL = "EMAIL"
    TELEGRAM = "TELEGRAM"
