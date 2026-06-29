from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.department import Department


def department_to_dict(department: Department) -> dict[str, Any]:
    return {
        "id": department.id,
        "name": department.name,
        "code": department.code,
        "is_active": department.is_active,
        "created_at": department.created_at,
        "updated_at": department.updated_at,
    }


def get_department_or_404(db: Session, department_id: int) -> Department:
    department = db.get(Department, department_id)
    if department is None:
        raise AppError(code="department_not_found", message="部门不存在。", status_code=404)
    return department


def ensure_department_code_available(
    db: Session,
    code: str,
    *,
    excluding_department_id: int | None = None,
) -> None:
    stmt = select(Department.id).where(Department.code == code)
    if excluding_department_id is not None:
        stmt = stmt.where(Department.id != excluding_department_id)
    if db.scalar(stmt) is not None:
        raise AppError(code="department_code_exists", message="部门编码已存在。", status_code=409)


def ensure_active_department(db: Session, department_id: int) -> Department:
    department = get_department_or_404(db, department_id)
    if not department.is_active:
        raise AppError(code="department_disabled", message="部门已停用，不能用于新的授权范围。", status_code=422)
    return department


def create_department(db: Session, payload: Any) -> Department:
    ensure_department_code_available(db, payload.code)
    department = Department(name=payload.name, code=payload.code, is_active=True)
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


def list_departments(
    db: Session,
    *,
    include_inactive: bool = True,
    page: int = 1,
    page_size: int = 100,
) -> tuple[list[Department], int]:
    stmt = select(Department)
    if not include_inactive:
        stmt = stmt.where(Department.is_active.is_(True))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(Department.is_active.desc(), Department.updated_at.desc(), Department.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total


def update_department(db: Session, *, department_id: int, payload: Any) -> Department:
    department = get_department_or_404(db, department_id)
    updates = payload.model_dump(exclude_unset=True)
    if "code" in updates and updates["code"] != department.code:
        ensure_department_code_available(db, updates["code"], excluding_department_id=department.id)
    for key, value in updates.items():
        setattr(department, key, value)
    db.commit()
    db.refresh(department)
    return department


def set_department_active(db: Session, *, department_id: int, is_active: bool) -> Department:
    department = get_department_or_404(db, department_id)
    department.is_active = is_active
    db.commit()
    db.refresh(department)
    return department
