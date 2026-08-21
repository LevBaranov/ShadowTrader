import uuid
from typing import List, Optional, Iterable

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.brokers_account import BrokersAccount
from src.db.models.users_broker import UsersBroker


class BrokersAccountRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_broker(self, users_broker_id: uuid.UUID) -> List[BrokersAccount]:
        result = await self.session.execute(
            select(BrokersAccount).where(
                BrokersAccount.users_broker_id == users_broker_id,
                BrokersAccount.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def get_for_user(
        self, account_pk: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[BrokersAccount]:
        """Вернуть аккаунт по его PK только если он принадлежит пользователю
        (через связь brokers_account -> users_broker)."""
        result = await self.session.execute(
            select(BrokersAccount)
            .join(UsersBroker, BrokersAccount.users_broker_id == UsersBroker.id)
            .where(
                BrokersAccount.id == account_pk,
                UsersBroker.user_id == user_id,
                BrokersAccount.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def sync_accounts(
        self, users_broker_id: uuid.UUID, accounts: Iterable[tuple[str, str]]
    ) -> List[BrokersAccount]:
        """Синхронизировать счета брокера с актуальным списком.

        accounts — итерируемое из (account_id, account_name). Новые создаются,
        существующие обновляются, пропавшим у брокера проставляется deleted_at
        (на счета ссылаются стратегии — физически не удаляем).
        Возвращает актуальный (не удалённый) список счетов.
        """
        result = await self.session.execute(
            select(BrokersAccount).where(
                BrokersAccount.users_broker_id == users_broker_id
            )
        )
        existing = {row.account_id: row for row in result.scalars().all()}
        incoming = dict(accounts)

        for account_id, account_name in incoming.items():
            row = existing.get(account_id)
            if row is None:
                self.session.add(
                    BrokersAccount(
                        users_broker_id=users_broker_id,
                        account_id=account_id,
                        account_name=account_name,
                    )
                )
            else:
                row.account_name = account_name
                row.deleted_at = None
                row.updated_at = func.now()

        for account_id, row in existing.items():
            if account_id not in incoming:
                if row.deleted_at is None:
                    row.deleted_at = func.now()
                row.updated_at = func.now()

        await self.session.commit()
        return await self.get_by_broker(users_broker_id)
