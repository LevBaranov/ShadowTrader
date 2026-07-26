import uuid
from typing import List

from starlette.concurrency import run_in_threadpool

from src.core.crypto import encrypt_token, decrypt_token
from src.db.models.brokers_account import BrokersAccount
from src.db.models.users_broker import UsersBroker
from src.db.repositories.brokers_account_repository import BrokersAccountRepository
from src.db.repositories.users_broker_repository import UsersBrokerRepository
from src.db.repositories.users_strategy_repository import UsersStrategyRepository
from src.models.broker_names import BrokerNames


class BrokerNotFoundError(Exception):
    """Брокер не найден у пользователя."""


class BrokerService:
    def __init__(
        self,
        broker_repo: UsersBrokerRepository,
        accounts_repo: BrokersAccountRepository,
        broker_client_factory,
        strategy_repo: UsersStrategyRepository = None,
    ):
        self.broker_repo = broker_repo
        self.accounts_repo = accounts_repo
        self.strategy_repo = strategy_repo
        # Фабрика клиента брокера (напр. TBroker). Ядро/сервис не завязано на конкретную реализацию.
        self.broker_client_factory = broker_client_factory

    async def save_broker_settings(
        self,
        user,
        broker_name: BrokerNames,
        token: str,
        sandbox: bool,
    ) -> UsersBroker:
        """Сохранить настройки брокера пользователя.

        Перед сохранением токен проверяется реальным запросом к брокеру —
        невалидный токен (BrokerAuthError) до БД не доходит.
        Токен шифруется здесь, до попадания в репозиторий/БД — в открытом виде
        он в хранилище не уходит.
        """
        client = self.broker_client_factory(token=token, sandbox=sandbox)
        # Запрос к брокеру синхронный (блокирующий gRPC) — уводим в threadpool.
        # Бросает BrokerAuthError, если токен недействителен.
        await run_in_threadpool(client.get_all_accounts)

        encrypted_token = encrypt_token(token)
        return await self.broker_repo.upsert(
            user_id=user.id,
            broker_name=broker_name,
            encrypted_token=encrypted_token,
            sandbox=sandbox,
        )

    async def list_brokers(self, user) -> List[UsersBroker]:
        """Список брокеров пользователя (без токенов)."""
        return await self.broker_repo.list_for_user(user.id)

    async def get_broker_accounts(
        self, user, broker_id: uuid.UUID
    ) -> List[BrokersAccount]:
        """Вернуть аккаунты пользователя у брокера из БД.

        Если в БД аккаунтов ещё нет — прозрачно «прогреваем» их: запрашиваем у
        брокера, сохраняем в БД и возвращаем. Всё в рамках одного запроса.
        """
        broker = await self.broker_repo.get_by_id_for_user(broker_id, user.id)
        if broker is None:
            raise BrokerNotFoundError(f"Broker {broker_id} not found for user {user.id}")

        accounts = await self.accounts_repo.get_by_broker(broker.id)
        if accounts:
            return accounts

        return await self._sync_accounts_from_broker(broker)

    async def refresh_broker_accounts(
        self, user, broker_id: uuid.UUID
    ) -> List[BrokersAccount]:
        """Принудительно обновить счета из брокера.

        Новые счета создаются, пропавшие помечаются deleted (не удаляются —
        на них могут ссылаться стратегии).
        """
        broker = await self.broker_repo.get_by_id_for_user(broker_id, user.id)
        if broker is None:
            raise BrokerNotFoundError(f"Broker {broker_id} not found for user {user.id}")

        return await self._sync_accounts_from_broker(broker)

    async def get_busy_account_ids(self, accounts: List[BrokersAccount]) -> set:
        """Id счетов из переданных, на которых уже есть стратегия."""
        if not self.strategy_repo or not accounts:
            return set()
        return await self.strategy_repo.get_busy_account_ids(
            [account.id for account in accounts]
        )

    async def _sync_accounts_from_broker(self, broker: UsersBroker) -> List[BrokersAccount]:
        """Запросить счета у брокера и синхронизировать их с БД."""
        token = decrypt_token(broker.broker_token)
        client = self.broker_client_factory(token=token, sandbox=broker.sandbox)

        # Обращение к брокеру синхронное (блокирующий gRPC) — уводим в threadpool.
        broker_accounts = await run_in_threadpool(client.get_all_accounts)

        return await self.accounts_repo.sync_accounts(
            broker.id,
            [(acc.id, acc.name) for acc in broker_accounts],
        )
