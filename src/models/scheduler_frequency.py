from enum import Enum

class ScheduleFrequency(str, Enum):
    DAILY = "Раз в день"
    WEEKLY = "Раз в неделю"
    MONTHLY = "Раз в 30 дней"
    QUARTERLY = "Раз в квартал"
