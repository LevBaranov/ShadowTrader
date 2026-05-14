from src.config import settings
from src.models.config import UserIndexBindingsConfig
from src.db.models.user import User


def get_user_strategies(user: User) -> UserIndexBindingsConfig | None:

    user_telegram_id = user.telegram_id

    user_config = [user for user in settings.users if user.telegram_id == user_telegram_id]

    if (user_config[0].index_bindings
            and user_config[0].index_bindings.index_name
            and user_config[0].index_bindings.broker_account_id):
        return user_config[0].index_bindings
    else:
        return None