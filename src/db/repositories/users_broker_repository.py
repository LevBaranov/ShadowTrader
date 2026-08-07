import uuid
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.users_broker import UsersBroker
from src.models.broker_names import BrokerNames


class UsersBrokerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_user(self, user_id: uuid.UUID) -> List[UsersBroker]:
        result = await self.session.execute(
            select(UsersBroker).where(UsersBroker.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_by_id_for_user(
        self, broker_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[UsersBroker]:
        result = await self.session.execute(
            select(UsersBroker).where(
                UsersBroker.id == broker_id,
                UsersBroker.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_user_and_name(
        self, user_id: uuid.UUID, broker_name: BrokerNames
    ) -> Optional[UsersBroker]:
        result = await self.session.execute(
            select(UsersBroker).where(
                UsersBroker.user_id == user_id,
                UsersBroker.broker_name == broker_name,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        user_id: uuid.UUID,
        broker_name: BrokerNames,
        encrypted_token: str,
        sandbox: bool,
        commission: Decimal | None = None,
    ) -> UsersBroker:
        """Создать или обновить настройки брокера пользователя.

        Токен ожидается уже зашифрованным — репозиторий не занимается шифрованием.
        commission=None — не менять (у нового брокера останется значение по умолчанию).
        """
        broker = await self.get_by_user_and_name(user_id, broker_name)
        if broker is None:
            broker = UsersBroker(
                user_id=user_id,
                broker_name=broker_name,
                broker_token=encrypted_token,
                sandbox=sandbox,
            )
            if commission is not None:
                broker.commission = commission
            self.session.add(broker)
        else:
            broker.broker_token = encrypted_token
            broker.sandbox = sandbox
            if commission is not None:
                broker.commission = commission

        await self.session.commit()
        await self.session.refresh(broker)
        return broker

    async def update_commission(
        self, broker_id: uuid.UUID, user_id: uuid.UUID, commission: Decimal
    ) -> Optional[UsersBroker]:
        """Поменять комиссию брокера. None — брокера у пользователя нет."""
        broker = await self.get_by_id_for_user(broker_id, user_id)
        if broker is None:
            return None

        broker.commission = commission

        await self.session.commit()
        await self.session.refresh(broker)
        return broker
