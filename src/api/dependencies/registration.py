from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.security import hash_password
from src.core.registration_service import RegistrationService
from src.db.database import get_session
from src.db.repositories.auth_identity_repository import AuthIdentityRepository
from src.services.email import EmailService


def get_registration_service(db: AsyncSession = Depends(get_session)) -> RegistrationService:
    return RegistrationService(
        identity_repo=AuthIdentityRepository(db),
        email_service=EmailService(),
        password_hasher=hash_password,
    )
