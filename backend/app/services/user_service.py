from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_password
from app.domain.enums import AccountType, ContentLevel
from app.models.user import User


def user_to_admin_dict(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "account_type": user.account_type,
        "content_level": user.content_level,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise AppError(code="not_found", message="账号不存在。", status_code=404)
    return user


def ensure_username_available(db: Session, username: str, *, excluding_user_id: int | None = None) -> None:
    stmt = select(User.id).where(User.username == username)
    if excluding_user_id is not None:
        stmt = stmt.where(User.id != excluding_user_id)
    if db.scalar(stmt) is not None:
        raise AppError(code="username_exists", message="用户名已存在。", status_code=409)


def validate_role_level(account_type: str, content_level: str) -> None:
    if account_type == AccountType.ADMIN.value:
        raise AppError(code="admin_account_not_manageable", message="此入口只管理员工账号。", status_code=422)
    if account_type == AccountType.GENERAL_USER.value and content_level != ContentLevel.GENERAL.value:
        raise AppError(code="invalid_user_role", message="通用权限员工只能使用通用级权限。", status_code=422)
    if account_type == AccountType.FULL_USER.value and content_level != ContentLevel.FULL.value:
        raise AppError(code="invalid_user_role", message="完整权限员工必须使用全量级权限。", status_code=422)


def create_user(db: Session, payload: Any) -> User:
    ensure_username_available(db, payload.username)
    validate_role_level(payload.account_type.value, payload.content_level.value)
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        account_type=payload.account_type.value,
        content_level=payload.content_level.value,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session, *, page: int = 1, page_size: int = 20) -> tuple[list[User], int]:
    stmt = select(User)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(User.updated_at.desc(), User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total


def update_user(db: Session, *, user_id: int, payload: Any) -> User:
    user = get_user_or_404(db, user_id)
    if user.account_type == AccountType.ADMIN.value:
        raise AppError(code="admin_account_not_manageable", message="此入口只管理员工账号。", status_code=422)
    updates = payload.model_dump(exclude_unset=True, mode="json")
    if "username" in updates:
        ensure_username_available(db, updates["username"], excluding_user_id=user.id)

    next_account_type = updates.get("account_type", user.account_type)
    next_content_level = updates.get("content_level", user.content_level)
    validate_role_level(next_account_type, next_content_level)

    for key, value in updates.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


def reset_user_password(db: Session, *, user_id: int, password: str) -> None:
    user = get_user_or_404(db, user_id)
    if user.account_type == AccountType.ADMIN.value:
        raise AppError(code="admin_account_not_manageable", message="此入口只管理员工账号。", status_code=422)
    user.password_hash = hash_password(password)
    db.commit()


def disable_user(db: Session, *, user_id: int, current_admin_id: int) -> User:
    if user_id == current_admin_id:
        raise AppError(code="cannot_disable_self", message="不能禁用当前登录账号。", status_code=409)
    user = get_user_or_404(db, user_id)
    if user.account_type == AccountType.ADMIN.value:
        raise AppError(code="admin_account_not_manageable", message="此入口只管理员工账号。", status_code=422)
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user
