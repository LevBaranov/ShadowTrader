from datetime import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.enums import AuthProvider
from src.db.models.auth_identity import AuthIdentity
from src.db.models.user import User


class AuthIdentityRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_provider_external_id(
            self, provider: AuthProvider, external_id: str
    ) -> AuthIdentity | None:
        stmt = select(AuthIdentity).where(
            AuthIdentity.provider == provider,
            AuthIdentity.external_id == external_id,
        )
        return await self.db.scalar(stmt)

    async def create_user_with_identity(
            self,
            provider: AuthProvider,
            external_id: str,
            password_hash: str | None = None,
            verified_at: datetime | None = None,
    ) -> AuthIdentity:
        """Создать пользователя вместе с первым способом входа (одна транзакция)."""
        user = User()
        identity = AuthIdentity(
            user=user,
            provider=provider,
            external_id=external_id,
            password_hash=password_hash,
            verified_at=verified_at,
        )

        self.db.add(user)
        self.db.add(identity)
        await self.db.commit()
        await self.db.refresh(identity)

        return identity

    async def add_identity(
            self,
            user_id: uuid.UUID,
            provider: AuthProvider,
            external_id: str,
            verified_at: datetime | None = None,
            password_hash: str | None = None,
    ) -> AuthIdentity:
        """Добавить способ входа существующему пользователю."""
        identity = AuthIdentity(
            user_id=user_id,
            provider=provider,
            external_id=external_id,
            verified_at=verified_at,
            password_hash=password_hash,
        )

        self.db.add(identity)
        await self.db.commit()
        await self.db.refresh(identity)

        return identity

    async def list_user_identities(self, user_id: uuid.UUID) -> list[AuthIdentity]:
        stmt = select(AuthIdentity).where(AuthIdentity.user_id == user_id)
        result = await self.db.scalars(stmt)
        return list(result)

    async def delete_identity(self, identity: AuthIdentity) -> None:
        await self.db.delete(identity)
        await self.db.commit()

    async def save(self) -> None:
        """Зафиксировать изменения в загруженных сущностях."""
        await self.db.commit()
