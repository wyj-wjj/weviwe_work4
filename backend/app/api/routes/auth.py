from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.errors import AppError
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.user import UserPublic


router = APIRouter(prefix="/api/auth", tags=["auth"])


def public_user(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        account_type=user.account_type,
        content_level=user.content_level,
    )


def invalid_credentials_error() -> AppError:
    return AppError(code="invalid_credentials", message="用户名或密码错误。", status_code=401)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise invalid_credentials_error()
    if not user.is_active:
        raise AppError(code="account_disabled", message="账号已被禁用，请联系管理员。", status_code=403)

    token = create_access_token(
        subject=str(user.id),
        account_type=user.account_type,
        content_level=user.content_level,
    )
    return LoginResponse(access_token=token, user=public_user(user))


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)) -> UserPublic:
    return public_user(current_user)
