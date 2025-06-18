from .loader import ConfigLoader

# Загружаем конфиг один раз при первом импорте config
ConfigLoader.load()
settings = ConfigLoader.config

