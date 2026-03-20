from .loader import ConfigLoader
from .db_settings import DBSettings

# Загружаем конфиг один раз при первом импорте config
ConfigLoader.load()
settings = ConfigLoader.config

db_settings = DBSettings()

