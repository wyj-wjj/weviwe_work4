from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_dashscope_client, require_admin
from app.core.errors import AppError
from app.db.session import get_db
from app.domain.enums import QuestionStatus
from app.models.user import User
from app.schemas.quiz import QuizGenerateRequest, QuizQuestionCreate, QuizQuestionUpdate, QuizSubmitRequest
from app.services.quiz_service import (
    approve_quiz_question,
    create_quiz_question,
    generate_candidate_questions_for_content_version,
    get_employee_quiz_questions_by_ids,
    list_employee_quiz_questions,
    list_quiz_generation_batches,
    list_quiz_questions,
    list_quiz_sets,
    quiz_generation_batch_to_dict,
    quiz_set_to_dict,
    quiz_to_dict,
    related_content_projection,
    reject_quiz_question,
    set_quiz_status,
    update_quiz_question,
)


router = APIRouter(tags=["quiz"])


@router.post("/api/admin/quiz-questions", status_code=201)
def admin_create_quiz_question(
    payload: QuizQuestionCreate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return quiz_to_dict(create_quiz_question(db, payload))


@router.get("/api/admin/quiz-questions")
def admin_list_quiz_questions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    items, total = list_quiz_questions(db, page=page, page_size=page_size)
    return {
        "items": [quiz_to_dict(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/api/admin/quiz-questions/{question_id}")
def admin_update_quiz_question(
    question_id: int,
    payload: QuizQuestionUpdate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return quiz_to_dict(update_quiz_question(db, question_id=question_id, payload=payload))


@router.post("/api/admin/quiz-questions/{question_id}/enable")
def admin_enable_quiz_question(
    question_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return quiz_to_dict(set_quiz_status(db, question_id=question_id, status=QuestionStatus.ENABLED))


@router.post("/api/admin/quiz-questions/{question_id}/disable")
def admin_disable_quiz_question(
    question_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return quiz_to_dict(set_quiz_status(db, question_id=question_id, status=QuestionStatus.DISABLED))


@router.post("/api/admin/quiz-questions/{question_id}/approve")
def admin_approve_quiz_question(
    question_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return quiz_to_dict(approve_quiz_question(db, question_id=question_id))


@router.post("/api/admin/quiz-questions/{question_id}/reject")
def admin_reject_quiz_question(
    question_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return quiz_to_dict(reject_quiz_question(db, question_id=question_id))


@router.get("/api/admin/quiz-generation-batches")
def admin_list_quiz_generation_batches(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    items, total = list_quiz_generation_batches(db, page=page, page_size=page_size)
    return {
        "items": [quiz_generation_batch_to_dict(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/api/admin/quiz-sets")
def admin_list_quiz_sets(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    items, total = list_quiz_sets(db, page=page, page_size=page_size)
    return {
        "items": [quiz_set_to_dict(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/api/admin/contents/{content_id}/versions/{version_id}/generate-quiz")
def admin_generate_quiz_for_content_version(
    content_id: int,
    version_id: int,
    payload: QuizGenerateRequest | None = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    dashscope_client=Depends(get_dashscope_client),
) -> dict[str, Any]:
    request = payload or QuizGenerateRequest()
    batch = generate_candidate_questions_for_content_version(
        db,
        content_id=content_id,
        version_id=version_id,
        admin=admin,
        dashscope_client=dashscope_client,
        requested_count=request.requested_count,
        create_quiz_set=request.create_quiz_set,
    )
    return quiz_generation_batch_to_dict(batch)


@router.get("/api/app/quiz")
def app_get_quiz(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    questions = list_employee_quiz_questions(db, current_user)
    return {
        "items": [
            quiz_to_dict(question, include_answer=False, user=current_user)
            for question in questions
        ]
    }


@router.post("/api/app/quiz/submit")
def app_submit_quiz(
    payload: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    allowed_by_id = get_employee_quiz_questions_by_ids(
        db,
        current_user,
        [answer.question_id for answer in payload.answers],
    )
    results = []
    for answer in payload.answers:
        question = allowed_by_id.get(answer.question_id)
        if question is None:
            raise AppError(code="not_found", message="Question not found.", status_code=404)
        relation = related_content_projection(question, user=current_user)
        results.append(
            {
                "question_id": question.id,
                "selected_answer": answer.selected_answer,
                "is_correct": answer.selected_answer == question.answer,
                "correct_answer": question.answer,
                "explanation": question.explanation,
                **relation,
            }
        )
    return {"results": results}
