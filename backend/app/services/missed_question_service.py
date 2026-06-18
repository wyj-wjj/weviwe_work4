from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domain.enums import MissedQuestionStatus
from app.models.missed_question import MissedQuestion
from app.models.user import User


def record_missed_question(db: Session, *, question: str, user: User) -> MissedQuestion:
    missed = MissedQuestion(
        question=question,
        user_id=user.id,
        account_type=user.account_type,
        content_level=user.content_level,
        status=MissedQuestionStatus.NEW.value,
    )
    db.add(missed)
    db.commit()
    db.refresh(missed)
    return missed


def missed_question_to_dict(missed: MissedQuestion) -> dict[str, Any]:
    return {
        "id": missed.id,
        "question": missed.question,
        "user_id": missed.user_id,
        "username": missed.user.username if missed.user else None,
        "account_type": missed.account_type,
        "content_level": missed.content_level,
        "asked_at": missed.asked_at,
        "status": missed.status,
        "handled_at": missed.handled_at,
    }


def list_missed_questions(
    db: Session,
    *,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[MissedQuestion], int]:
    stmt = select(MissedQuestion)
    if status:
        stmt = stmt.where(MissedQuestion.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(MissedQuestion.asked_at.desc(), MissedQuestion.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total


def mark_missed_question_handled(db: Session, *, question_id: int) -> MissedQuestion:
    missed = db.get(MissedQuestion, question_id)
    if missed is None:
        raise AppError(code="not_found", message="Missed question not found.", status_code=404)
    missed.status = MissedQuestionStatus.HANDLED.value
    missed.handled_at = datetime.now(UTC)
    db.commit()
    db.refresh(missed)
    return missed
