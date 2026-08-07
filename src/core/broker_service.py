import uuid
from decimal import Decimal
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


class BrokerValidationError(Exception):
    """Некорректные настройки брокера."""


def _validate_commission(commission: Decimal) -> None:
    """Комиссия — доля, а не проценты: 0.003 (0,3 %), но не 0.3 и не 3.

    Верхняя граница отсекает случай, когда клиент прислал проценты вместо доли:
    комиссии в 100 % не бывает, а вот «0.3» вместо «0.003» — типичная ошибка.
    """
    if commission < 0 or commission >= 1:
        raise BrokerValidationError(
            "commission must be a fraction in [0, 1): 0.003 means 0.3%"
        )


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
        commission: Decimal | None = None,
    ) -> UsersBroker:
        """Сохранить настройки брокера пользователя.

        Перед сохранением токен проверяется реальным запросом к брокеру —
        невалидный токен (BrokerAuthError) до БД не доходит.
        Токен шифруется здесь, до попадания в репозиторий/БД — в открытом виде
        он в хранилище не уходит.

        commission=None — комиссию не меняем: у нового брокера останется значение
        по умолчанию, у существующего — то, что уже сохранено.
        """
        if commission is not None:
            _validate_commission(commission)

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
            commission=commission,
        )

    async def update_commission(
        self, user, broker_id: uuid.UUID, commission: Decimal
    ) -> UsersBroker:
        """Поменять комиссию брокера — без токена и без обращения к брокеру."""
        _validate_commission(commission)

        broker = await self.broker_repo.update_commission(
            broker_id, user.id, commission
        )
        if broker is None:
            raise BrokerNotFoundError(str(broker_id))

        return broker

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

    async def list_all_accounts(self, user) -> List[BrokersAccount]:
        """Все счета пользователя по всем его брокерам одним списком.

        Нужен там, где брокер не важен: выбор счёта для проверки облигаций,
        раздел настроек. Счета брокера, которых ещё нет в БД, подтягиваются.
        """
        accounts: List[BrokersAccount] = []
        for broker in await self.broker_repo.list_for_user(user.id):
            broker_accounts = await self.accounts_repo.get_by_broker(broker.id)
            if not broker_accounts:
                broker_accounts = await self._sync_accounts_from_broker(broker)
            accounts.extend(broker_accounts)

        return accounts

    async def refresh_all_accounts(self, user) -> List[BrokersAccount]:
        """Принудительно обновить счета по всем брокерам пользователя."""
        accounts: List[BrokersAccount] = []
        for broker in await self.broker_repo.list_for_user(user.id):
            accounts.extend(await self._sync_accounts_from_broker(broker))

        return accounts

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
