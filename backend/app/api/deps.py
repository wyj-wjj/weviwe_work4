from collections.abc import Generator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.domain.enums import AccountType
from app.integrations.dashscope import create_dashscope_client
from app.integrations.milvus import create_milvus_client
from app.models.user import User
from app.services.permission_service import scope_is_visible, visible_levels_for


bearer_scheme = HTTPBearer(auto_error=False)


def authentication_error() -> AppError:
    return AppError(code="authentication_required", message="请先登录。", status_code=401)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise authentication_error()
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload.subject)
    except (TypeError, ValueError):
        raise authentication_error() from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise authentication_error()
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.account_type != AccountType.ADMIN.value:
        raise AppError(code="admin_required", message="仅管理员可访问。", status_code=403)
    return current_user


def permitted_content_levels(user: User) -> set[str]:
    return visible_levels_for(user)


def ensure_content_visible(
    user: User,
    permission_level: str,
    *,
    scope_type: str = "global",
    department_id: int | None = None,
) -> None:
    if permission_level not in permitted_content_levels(user) or not scope_is_visible(
        user,
        scope_type,
        department_id,
    ):
        raise AppError(code="permission_denied", message="无权查看该内容", status_code=403)


def db_session_dependency() -> Generator[Session, None, None]:
    yield from get_db()


def get_dashscope_client():
    return create_dashscope_client(Settings())


def get_milvus_client():
    return create_milvus_client(Settings())
