from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domain.enums import QuestionStatus
from app.models.quiz import QuizQuestion
from app.models.user import User
from app.services.content_service import visible_levels_for


def quiz_to_dict(question: QuizQuestion, *, include_answer: bool = True) -> dict[str, Any]:
    payload = {
        "id": question.id,
        "question": question.question,
        "options": question.options,
        "explanation": question.explanation,
        "related_content_id": question.related_content_id,
        "related_content_title": question.related_content.title if question.related_content else None,
        "permission_level": question.permission_level,
        "status": question.status,
        "updated_at": question.updated_at,
    }
    if include_answer:
        payload["answer"] = question.answer
    return payload


def get_quiz_or_404(db: Session, question_id: int) -> QuizQuestion:
    question = db.get(QuizQuestion, question_id)
    if question is None:
        raise AppError(code="not_found", message="测验题不存在。", status_code=404)
    return question


def create_quiz_question(db: Session, payload: Any) -> QuizQuestion:
    question = QuizQuestion(**payload.model_dump(mode="json"))
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def update_quiz_question(db: Session, *, question_id: int, payload: Any) -> QuizQuestion:
    question = get_quiz_or_404(db, question_id)
    for key, value in payload.model_dump(exclude_unset=True, mode="json").items():
        setattr(question, key, value)
    db.commit()
    db.refresh(question)
    return question


def set_quiz_status(db: Session, *, question_id: int, status: QuestionStatus) -> QuizQuestion:
    question = get_quiz_or_404(db, question_id)
    question.status = status.value
    db.commit()
    db.refresh(question)
    return question


def list_quiz_questions(db: Session, *, page: int = 1, page_size: int = 20) -> tuple[list[QuizQuestion], int]:
    stmt = select(QuizQuestion)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(QuizQuestion.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return list(items), total


def list_employee_quiz_questions(db: Session, user: User) -> list[QuizQuestion]:
    stmt = (
        select(QuizQuestion)
        .where(QuizQuestion.status == QuestionStatus.ENABLED.value)
        .where(QuizQuestion.permission_level.in_(visible_levels_for(user)))
        .order_by(QuizQuestion.id.asc())
        .limit(10)
    )
    return list(db.scalars(stmt).all())
