# Импортируем все модели, чтобы при обращении к любой из них были
# зарегистрированы все мапперы: relationship() ссылается на классы по имени
# (например, User -> "Task"), и SQLAlchemy падает, если класс не импортирован.
from .user import User
from .auth_identity import AuthIdentity
from .telegram_link_request import TelegramLinkRequest
from .task import Task, TaskResult
from .users_broker import UsersBroker
from .brokers_account import BrokersAccount
from .stock_market_index import StockMarketsIndex
from .users_strategy import UsersStrategy
