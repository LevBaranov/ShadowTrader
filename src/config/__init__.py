from .loader import ConfigLoader
from .settings import DBSettings, APISettings

# Загружаем конфиг один раз при первом импорте config
ConfigLoader.load()
settings = ConfigLoader.config

db_settings = DBSettings()
api_settings = APISettings()
