from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
import uuid

from src.config import api_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)

def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": user_id,
        "iss": api_settings.JWT_ISSUER,
        "aud": api_settings.JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=api_settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": str(uuid.uuid4()),
    }

    return jwt.encode(
        payload,
        api_settings.SECRET_KEY,
        algorithm=api_settings.ALGORITHM,
    )

def decode_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token,
            api_settings.SECRET_KEY,
            algorithms=[api_settings.ALGORITHM],
            audience=api_settings.JWT_AUDIENCE,
        )

        if payload.get("iss") != api_settings.JWT_ISSUER:
            raise JWTError("Invalid issuer")

        return payload

    except JWTError:
        return None