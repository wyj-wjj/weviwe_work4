from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.services.department_service import (
    create_department,
    department_to_dict,
    list_departments,
    set_department_active,
    update_department,
)


router = APIRouter(tags=["departments"])


@router.post("/api/admin/departments", status_code=201)
def admin_create_department(
    payload: DepartmentCreate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return department_to_dict(create_department(db, payload))


@router.get("/api/admin/departments")
def admin_list_departments(
    include_inactive: bool = True,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    items, total = list_departments(
        db,
        include_inactive=include_inactive,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [department_to_dict(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/api/admin/departments/{department_id}")
def admin_update_department(
    department_id: int,
    payload: DepartmentUpdate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return department_to_dict(update_department(db, department_id=department_id, payload=payload))


@router.post("/api/admin/departments/{department_id}/disable")
def admin_disable_department(
    department_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return department_to_dict(set_department_active(db, department_id=department_id, is_active=False))


@router.post("/api/admin/departments/{department_id}/enable")
def admin_enable_department(
    department_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return department_to_dict(set_department_active(db, department_id=department_id, is_active=True))
