from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError
from app.domain.enums import ContentLevel, ContentStatus, QuestionStatus
from app.models.content import Content
from app.models.quiz import QuizQuestion
from app.models.user import User
from app.services.content_service import visible_levels_for


def visible_related_content(question: QuizQuestion, user: User) -> Content | None:
    content = question.related_content
    if (
        content is None
        or content.status != ContentStatus.PUBLISHED.value
        or content.current_version_id is None
        or content.permission_level not in visible_levels_for(user)
    ):
        return None
    return content


def related_content_projection(question: QuizQuestion, *, user: User | None = None) -> dict[str, Any]:
    content = question.related_content if user is None else visible_related_content(question, user)
    return {
        "related_content_id": question.related_content_id if user is None else (content.id if content else None),
        "related_content_title": content.title if content else None,
        "related_content_type": content.content_type if content else None,
    }


def quiz_to_dict(
    question: QuizQuestion,
    *,
    include_answer: bool = True,
    user: User | None = None,
) -> dict[str, Any]:
    payload = {
        "id": question.id,
        "question": question.question,
        "options": question.options,
        "explanation": question.explanation,
        "permission_level": question.permission_level,
        "status": question.status,
        "updated_at": question.updated_at,
        **related_content_projection(question, user=user),
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
    items = db.scalars(
        stmt.options(joinedload(QuizQuestion.related_content))
        .order_by(QuizQuestion.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total


def _load_employee_quiz_questions(
    db: Session,
    *,
    permission_level: ContentLevel,
    limit: int,
    offset: int = 0,
) -> list[QuizQuestion]:
    stmt = (
        select(QuizQuestion)
        .options(joinedload(QuizQuestion.related_content))
        .where(QuizQuestion.status == QuestionStatus.ENABLED.value)
        .where(QuizQuestion.permission_level == permission_level.value)
        .order_by(QuizQuestion.id.asc())
        .limit(limit)
    )
    if offset:
        stmt = stmt.offset(offset)
    return list(db.scalars(stmt).all())


def list_employee_quiz_questions(db: Session, user: User) -> list[QuizQuestion]:
    if user.account_type not in {"admin", "full_user"}:
        return _load_employee_quiz_questions(
            db,
            permission_level=ContentLevel.GENERAL,
            limit=10,
        )

    reserved_full = _load_employee_quiz_questions(
        db,
        permission_level=ContentLevel.FULL,
        limit=1,
    )
    general_items = _load_employee_quiz_questions(
        db,
        permission_level=ContentLevel.GENERAL,
        limit=9 if reserved_full else 10,
    )
    selected = reserved_full + general_items
    if reserved_full and len(selected) < 10:
        selected.extend(
            _load_employee_quiz_questions(
                db,
                permission_level=ContentLevel.FULL,
                limit=10 - len(selected),
                offset=1,
            )
        )
    return selected


def get_employee_quiz_questions_by_ids(
    db: Session,
    user: User,
    question_ids: list[int],
) -> dict[int, QuizQuestion]:
    requested_ids = set(question_ids)
    if not requested_ids:
        return {}

    stmt = (
        select(QuizQuestion)
        .options(joinedload(QuizQuestion.related_content))
        .where(QuizQuestion.id.in_(requested_ids))
        .where(QuizQuestion.status == QuestionStatus.ENABLED.value)
        .where(QuizQuestion.permission_level.in_(visible_levels_for(user)))
    )
    questions = list(db.scalars(stmt).all())
    if len(questions) != len(requested_ids):
        raise AppError(code="not_found", message="Question not found.", status_code=404)
    return {question.id: question for question in questions}
