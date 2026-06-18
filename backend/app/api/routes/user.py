from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserPasswordReset, UserUpdate
from app.services.user_service import (
    create_user,
    disable_user,
    list_users,
    reset_user_password,
    update_user,
    user_to_admin_dict,
)


router = APIRouter(tags=["users"])


@router.post("/api/admin/users", status_code=201)
def admin_create_user(
    payload: UserCreate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return user_to_admin_dict(create_user(db, payload))


@router.get("/api/admin/users")
def admin_list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    items, total = list_users(db, page=page, page_size=page_size)
    return {
        "items": [user_to_admin_dict(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/api/admin/users/{user_id}")
def admin_update_user(
    user_id: int,
    payload: UserUpdate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return user_to_admin_dict(update_user(db, user_id=user_id, payload=payload))


@router.post("/api/admin/users/{user_id}/reset-password")
def admin_reset_user_password(
    user_id: int,
    payload: UserPasswordReset,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    reset_user_password(db, user_id=user_id, password=payload.password)
    return {"reset": True}


@router.post("/api/admin/users/{user_id}/disable")
def admin_disable_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return user_to_admin_dict(disable_user(db, user_id=user_id, current_admin_id=admin.id))
