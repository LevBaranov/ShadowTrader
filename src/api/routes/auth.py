from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import get_session
from src.db.enums import AuthProvider
from src.db.repositories.auth_identity_repository import AuthIdentityRepository
from src.api.dependencies.registration import get_registration_service
from src.api.security import (
    verify_password,
    create_access_token,
)
from src.core.registration_service import (
    RegistrationService,
    normalize_email,
    EmailAlreadyRegisteredError,
    RegistrationNotFoundError,
    InvalidCodeError,
    CodeExpiredError,
    TooManyAttemptsError,
    ResendCooldownError,
)
from src.services.email import EmailSendError
from src.models.api_user import (
    LoginSuccess,
    LoginRequest,
    RegisterRequest,
    RegisterSuccess,
    ConfirmEmailRequest,
    ResendCodeRequest,
)

router = APIRouter(prefix="/auth")

# В detail отдаём машиночитаемые коды — фронтенд сам маппит их на тексты.


@router.post("/login", response_model=LoginSuccess)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_session)) -> LoginSuccess:
    identity_repo = AuthIdentityRepository(db)
    identity = await identity_repo.get_by_provider_external_id(
        AuthProvider.EMAIL, normalize_email(data.email)
    )

    if not identity or not identity.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(data.password, identity.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if identity.verified_at is None:
        raise HTTPException(status_code=403, detail="email_not_verified")

    token = create_access_token(str(identity.user_id))

    return LoginSuccess(
        access_token=token,
        token_type="bearer"
    )


@router.post("/register", response_model=RegisterSuccess, status_code=201)
async def register(
    data: RegisterRequest,
    service: RegistrationService = Depends(get_registration_service),
) -> RegisterSuccess:
    try:
        await service.register(data.email, data.password)
    except EmailAlreadyRegisteredError:
        raise HTTPException(status_code=409, detail="email_already_registered")
    except EmailSendError:
        raise HTTPException(status_code=503, detail="email_send_failed")

    return RegisterSuccess(email=normalize_email(data.email))


@router.post("/register/confirm", response_model=LoginSuccess)
async def confirm_email(
    data: ConfirmEmailRequest,
    service: RegistrationService = Depends(get_registration_service),
) -> LoginSuccess:
    try:
        identity = await service.confirm(data.email, data.code)
    except (RegistrationNotFoundError, InvalidCodeError):
        raise HTTPException(status_code=400, detail="invalid_code")
    except CodeExpiredError:
        raise HTTPException(status_code=400, detail="code_expired")
    except TooManyAttemptsError:
        raise HTTPException(status_code=429, detail="too_many_attempts")

    # Почта подтверждена — сразу логиним, чтобы не гонять пользователя по формам.
    token = create_access_token(str(identity.user_id))

    return LoginSuccess(
        access_token=token,
        token_type="bearer"
    )


@router.post("/register/resend", response_model=RegisterSuccess)
async def resend_code(
    data: ResendCodeRequest,
    service: RegistrationService = Depends(get_registration_service),
) -> RegisterSuccess:
    try:
        await service.resend_code(data.email)
    except RegistrationNotFoundError:
        raise HTTPException(status_code=400, detail="invalid_code")
    except ResendCooldownError:
        raise HTTPException(status_code=429, detail="resend_cooldown")
    except EmailSendError:
        raise HTTPException(status_code=503, detail="email_send_failed")

    return RegisterSuccess(email=normalize_email(data.email))
