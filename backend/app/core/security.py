from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from pydantic import BaseModel

from app.core.config import Settings


password_hasher = PasswordHasher()


class TokenPayload(BaseModel):
    subject: str
    account_type: str
    content_level: str


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_access_token(
    *,
    subject: str,
    account_type: str,
    content_level: str,
    expires_delta: timedelta | None = None,
    expires_at: datetime | None = None,
    settings: Settings | None = None,
) -> str:
    resolved_settings = settings or Settings()
    expire = expires_at or datetime.now(UTC) + (expires_delta or timedelta(minutes=60))
    payload: dict[str, Any] = {
        "sub": subject,
        "account_type": account_type,
        "content_level": content_level,
        "exp": expire,
    }
    return jwt.encode(payload, resolved_settings.jwt_secret_key, algorithm="HS256")


def decode_access_token(token: str, settings: Settings | None = None) -> TokenPayload:
    resolved_settings = settings or Settings()
    try:
        payload = jwt.decode(token, resolved_settings.jwt_secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise ValueError("expired token") from exc
    except jwt.PyJWTError as exc:
        raise ValueError("invalid token") from exc

    subject = payload.get("sub")
    account_type = payload.get("account_type")
    content_level = payload.get("content_level")
    if not isinstance(subject, str) or not isinstance(account_type, str) or not isinstance(content_level, str):
        raise ValueError("invalid token payload")
    return TokenPayload(subject=subject, account_type=account_type, content_level=content_level)
