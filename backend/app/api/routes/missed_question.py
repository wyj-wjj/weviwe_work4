from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.user import User
from app.services.missed_question_service import (
    list_missed_questions,
    mark_missed_question_handled,
    missed_question_to_dict,
)


router = APIRouter(tags=["missed-questions"])


@router.get("/api/admin/missed-questions")
def admin_list_missed_questions(
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    items, total = list_missed_questions(db, status=status, page=page, page_size=page_size)
    return {
        "items": [missed_question_to_dict(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/api/admin/missed-questions/{question_id}/mark-handled")
def admin_mark_missed_question_handled(
    question_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return missed_question_to_dict(mark_missed_question_handled(db, question_id=question_id))
