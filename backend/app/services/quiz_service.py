import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError
from app.domain.enums import (
    ContentLevel,
    ContentStatus,
    QuestionStatus,
    QuizAction,
    QuizGenerationStatus,
    QuizReviewStatus,
    QuizSetStatus,
    QuizSourceType,
    UpdateLevel,
)
from app.integrations.dashscope import normalize_provider_error
from app.models.content import Content, ContentVersion
from app.models.quiz import QuizGenerationBatch, QuizQuestion, QuizQuestionSetItem, QuizSet
from app.models.user import User
from app.services.permission_service import scope_filter, scope_is_visible, visible_levels_for


QUIZ_GENERATION_PROMPT_VERSION = "quiz-generation-v1"
MAJOR_TOPIC_PRIORITY = 100
MEDIUM_UPDATE_PRIORITY = 50
EMPLOYEE_QUIZ_LIMIT = 10
EMPLOYEE_QUIZ_CANDIDATE_WINDOW = 100
OLDEST_SORT_TIME = datetime.min.replace(tzinfo=UTC)
QUIZ_SOURCE_INVALID_MESSAGES = {
    "source_content_missing": "源内容不存在，不能审核通过或启用该题目。",
    "source_content_offline": "源内容已下线，不能审核通过或启用该题目。",
    "source_content_inactive": "源内容未发布，不能审核通过或启用该题目。",
    "source_content_no_current_version": "源内容没有当前版本，不能审核通过或启用该题目。",
    "source_version_stale": "源版本已失效，不能审核通过或启用该题目。",
    "quiz_set_inactive": "专题测验包已停用，不能审核通过或启用该题目。",
}


def visible_related_content(question: QuizQuestion, user: User) -> Content | None:
    content = question.related_content
    if (
        content is None
        or content.status != ContentStatus.PUBLISHED.value
        or content.current_version_id is None
        or content.permission_level not in visible_levels_for(user)
        or not scope_is_visible(user, content.scope_type, content.department_id)
    ):
        return None
    if question.related_version_id is not None and question.related_version_id != content.current_version_id:
        return None
    return content


def quiz_source_invalid_reason(question: QuizQuestion) -> str | None:
    if question.related_content_id is None:
        return None

    content = question.related_content
    if content is None:
        return "source_content_missing"
    if content.status == ContentStatus.OFFLINE.value:
        return "source_content_offline"
    if content.status != ContentStatus.PUBLISHED.value:
        return "source_content_inactive"
    if content.current_version_id is None:
        return "source_content_no_current_version"
    if question.related_version_id is not None and question.related_version_id != content.current_version_id:
        return "source_version_stale"
    if question.set_items and not any(
        item.quiz_set is not None and item.quiz_set.status == QuizSetStatus.ACTIVE.value
        for item in question.set_items
    ):
        return "quiz_set_inactive"
    return None


def ensure_quiz_source_valid(question: QuizQuestion) -> None:
    reason = quiz_source_invalid_reason(question)
    if reason is None:
        return
    raise AppError(
        code="quiz_source_invalid",
        message=QUIZ_SOURCE_INVALID_MESSAGES[reason],
        status_code=409,
    )


def related_content_projection(question: QuizQuestion, *, user: User | None = None) -> dict[str, Any]:
    content = question.related_content if user is None else visible_related_content(question, user)
    return {
        "related_content_id": question.related_content_id if user is None else (content.id if content else None),
        "related_content_title": content.title if content else None,
        "related_content_type": content.content_type if content else None,
        "related_content_category": content.category if content else None,
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
    if user is None:
        source_invalid_reason = quiz_source_invalid_reason(question)
        payload.update(
            {
                "related_version_id": question.related_version_id,
                "source_type": question.source_type,
                "review_status": question.review_status,
                "generation_batch_id": question.generation_batch_id,
                "needs_review": question.needs_review,
                "review_reason": question.review_reason,
                "expires_at": question.expires_at,
                "priority": question.priority,
                "source_valid": source_invalid_reason is None,
                "source_invalid_reason": source_invalid_reason,
            }
        )
    if include_answer:
        payload["answer"] = question.answer
    return payload


def get_quiz_or_404(db: Session, question_id: int) -> QuizQuestion:
    question = db.execute(
        select(QuizQuestion)
        .options(
            joinedload(QuizQuestion.related_content),
            joinedload(QuizQuestion.set_items).joinedload(QuizQuestionSetItem.quiz_set),
        )
        .where(QuizQuestion.id == question_id)
    ).unique().scalar_one_or_none()
    if question is None:
        raise AppError(code="not_found", message="测验题不存在。", status_code=404)
    return question


def normalize_quiz_payload(db: Session, data: dict[str, Any]) -> dict[str, Any]:
    related_content_id = data.get("related_content_id")
    related_version_id = data.get("related_version_id")
    generation_batch_id = data.get("generation_batch_id")

    if generation_batch_id is not None and db.get(QuizGenerationBatch, generation_batch_id) is None:
        raise AppError(
            code="invalid_quiz_generation_batch",
            message="generation_batch_id does not exist.",
            status_code=422,
        )

    if related_content_id is None:
        if related_version_id is not None:
            version = db.get(ContentVersion, related_version_id)
            if version is not None:
                data["related_content_id"] = version.content_id
            return data
        if "related_content_id" in data and "related_version_id" not in data:
            data["related_version_id"] = None
        return data

    if related_version_id is None:
        content = db.get(Content, related_content_id)
        if content is not None and content.current_version_id is not None:
            data["related_version_id"] = content.current_version_id
        return data

    version = db.get(ContentVersion, related_version_id)
    if version is not None and version.content_id != related_content_id:
        raise AppError(
            code="invalid_quiz_source",
            message="related_version_id does not belong to related_content_id.",
            status_code=422,
        )
    return data


def create_quiz_question(db: Session, payload: Any) -> QuizQuestion:
    question = QuizQuestion(**normalize_quiz_payload(db, payload.model_dump(mode="json")))
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def update_quiz_question(db: Session, *, question_id: int, payload: Any) -> QuizQuestion:
    question = get_quiz_or_404(db, question_id)
    updates = normalize_quiz_payload(db, payload.model_dump(exclude_unset=True, mode="json"))
    for key, value in updates.items():
        setattr(question, key, value)
    db.commit()
    db.refresh(question)
    return question


def set_quiz_status(db: Session, *, question_id: int, status: QuestionStatus) -> QuizQuestion:
    question = get_quiz_or_404(db, question_id)
    if status == QuestionStatus.ENABLED:
        ensure_quiz_source_valid(question)
    question.status = status.value
    db.commit()
    db.refresh(question)
    return question


def approve_quiz_question(db: Session, *, question_id: int) -> QuizQuestion:
    question = get_quiz_or_404(db, question_id)
    ensure_quiz_source_valid(question)
    question.review_status = QuizReviewStatus.APPROVED.value
    question.status = QuestionStatus.ENABLED.value
    question.needs_review = False
    question.review_reason = None
    db.commit()
    db.refresh(question)
    return question


def reject_quiz_question(db: Session, *, question_id: int) -> QuizQuestion:
    question = get_quiz_or_404(db, question_id)
    question.review_status = QuizReviewStatus.REJECTED.value
    question.status = QuestionStatus.DISABLED.value
    question.needs_review = False
    db.commit()
    db.refresh(question)
    return question


def list_quiz_questions(db: Session, *, page: int = 1, page_size: int = 20) -> tuple[list[QuizQuestion], int]:
    stmt = select(QuizQuestion)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.options(
            joinedload(QuizQuestion.related_content),
            joinedload(QuizQuestion.set_items).joinedload(QuizQuestionSetItem.quiz_set),
        )
        .order_by(QuizQuestion.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).unique().all()
    return list(items), total


def _load_employee_quiz_questions(
    db: Session,
    *,
    permission_level: ContentLevel,
    visible_content_levels: set[str],
    user: User,
    limit: int,
    offset: int = 0,
) -> list[QuizQuestion]:
    now = datetime.now(UTC)
    stmt = (
        select(QuizQuestion)
        .outerjoin(Content, QuizQuestion.related_content_id == Content.id)
        .outerjoin(ContentVersion, Content.current_version_id == ContentVersion.id)
        .options(joinedload(QuizQuestion.related_content).joinedload(Content.current_version))
        .where(QuizQuestion.status == QuestionStatus.ENABLED.value)
        .where(QuizQuestion.review_status == QuizReviewStatus.APPROVED.value)
        .where(QuizQuestion.needs_review.is_(False))
        .where(QuizQuestion.permission_level == permission_level.value)
        .where(or_(QuizQuestion.expires_at.is_(None), QuizQuestion.expires_at > now))
        .where(visible_related_content_filter(visible_content_levels, user))
        .order_by(
            QuizQuestion.priority.desc(),
            ContentVersion.published_at.desc(),
            QuizQuestion.id.asc(),
        )
        .limit(limit)
    )
    if offset:
        stmt = stmt.offset(offset)
    return list(db.scalars(stmt).all())


def _load_employee_review_quiz_questions(
    db: Session,
    *,
    user: User,
    category: str | None = None,
    limit: int = 10,
) -> list[QuizQuestion]:
    now = datetime.now(UTC)
    stmt = (
        select(QuizQuestion)
        .outerjoin(Content, QuizQuestion.related_content_id == Content.id)
        .options(joinedload(QuizQuestion.related_content).joinedload(Content.current_version))
        .where(QuizQuestion.status == QuestionStatus.ENABLED.value)
        .where(QuizQuestion.review_status == QuizReviewStatus.APPROVED.value)
        .where(QuizQuestion.needs_review.is_(False))
        .where(QuizQuestion.permission_level.in_(visible_levels_for(user)))
        .where(or_(QuizQuestion.expires_at.is_(None), QuizQuestion.expires_at > now))
        .where(visible_related_content_filter(visible_levels_for(user), user))
        .order_by(QuizQuestion.priority.desc(), QuizQuestion.updated_at.desc(), QuizQuestion.id.asc())
        .limit(limit)
    )
    if category:
        stmt = stmt.where(Content.category == category)
    return list(db.scalars(stmt).all())


def _aware_sort_time(value: datetime | None) -> datetime:
    if value is None:
        return OLDEST_SORT_TIME
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _question_batch_id(question: QuizQuestion) -> int:
    if question.related_version_id is not None:
        return question.related_version_id
    content = question.related_content
    if content is not None and content.current_version_id is not None:
        return content.current_version_id
    if question.generation_batch_id is not None:
        return question.generation_batch_id
    return 0


def _question_group_key(question: QuizQuestion) -> tuple[int, str, int]:
    priority = question.priority or 0
    if question.related_version_id is not None:
        return (priority, "version", question.related_version_id)
    content = question.related_content
    if content is not None and content.current_version_id is not None:
        return (priority, "version", content.current_version_id)
    if question.generation_batch_id is not None:
        return (priority, "batch", question.generation_batch_id)
    return (priority, "standalone", 0)


def _question_group_time(question: QuizQuestion, mode: str) -> datetime:
    if mode == "latest":
        content = question.related_content
        current_version = content.current_version if content is not None else None
        published_at = current_version.published_at if current_version is not None else None
        if published_at is not None:
            return _aware_sort_time(published_at)
    return _aware_sort_time(question.updated_at)


def _stable_shuffle_key(refresh_seed: str, question: QuizQuestion) -> str:
    return hashlib.sha256(f"{refresh_seed}:{question.id}".encode("utf-8")).hexdigest()


def _sample_employee_quiz_questions(
    candidates: list[QuizQuestion],
    *,
    refresh_seed: str | None,
    mode: str,
    limit: int = EMPLOYEE_QUIZ_LIMIT,
) -> list[QuizQuestion]:
    if not refresh_seed:
        return candidates[:limit]

    groups: dict[tuple[int, str, int], list[QuizQuestion]] = {}
    for question in candidates:
        groups.setdefault(_question_group_key(question), []).append(question)

    def group_sort_key(item: tuple[tuple[int, str, int], list[QuizQuestion]]) -> tuple[int, datetime, int]:
        key, questions = item
        priority = key[0]
        group_time = max((_question_group_time(question, mode) for question in questions), default=OLDEST_SORT_TIME)
        batch_id = max((_question_batch_id(question) for question in questions), default=0)
        return (priority, group_time, batch_id)

    selected: list[QuizQuestion] = []
    for _key, questions in sorted(groups.items(), key=group_sort_key, reverse=True):
        selected.extend(sorted(questions, key=lambda question: (_stable_shuffle_key(refresh_seed, question), question.id)))
        if len(selected) >= limit:
            return selected[:limit]
    return selected


def visible_related_content_filter(visible_content_levels: set[str], user: User):
    return or_(
        QuizQuestion.related_content_id.is_(None),
        and_(
            Content.id.is_not(None),
            Content.status == ContentStatus.PUBLISHED.value,
            Content.current_version_id.is_not(None),
            Content.permission_level.in_(visible_content_levels),
            scope_filter(user, Content),
            or_(
                QuizQuestion.related_version_id.is_(None),
                QuizQuestion.related_version_id == Content.current_version_id,
            ),
        ),
    )


def list_employee_quiz_questions(
    db: Session,
    user: User,
    *,
    mode: str = "latest",
    category: str | None = None,
    refresh_seed: str | None = None,
) -> list[QuizQuestion]:
    if mode == "review":
        review_candidates = _load_employee_review_quiz_questions(
            db,
            user=user,
            category=category,
            limit=EMPLOYEE_QUIZ_CANDIDATE_WINDOW if refresh_seed else EMPLOYEE_QUIZ_LIMIT,
        )
        return _sample_employee_quiz_questions(
            review_candidates,
            refresh_seed=refresh_seed,
            mode=mode,
            limit=EMPLOYEE_QUIZ_LIMIT,
        )

    user_visible_content_levels = visible_levels_for(user)
    if user.account_type not in {"admin", "full_user"}:
        general_candidates = _load_employee_quiz_questions(
            db,
            permission_level=ContentLevel.GENERAL,
            visible_content_levels=user_visible_content_levels,
            user=user,
            limit=EMPLOYEE_QUIZ_CANDIDATE_WINDOW if refresh_seed else EMPLOYEE_QUIZ_LIMIT,
        )
        return _sample_employee_quiz_questions(
            general_candidates,
            refresh_seed=refresh_seed,
            mode=mode,
            limit=EMPLOYEE_QUIZ_LIMIT,
        )

    if refresh_seed:
        full_candidates = _load_employee_quiz_questions(
            db,
            permission_level=ContentLevel.FULL,
            visible_content_levels=user_visible_content_levels,
            user=user,
            limit=EMPLOYEE_QUIZ_CANDIDATE_WINDOW,
        )
        reserved_full = _sample_employee_quiz_questions(
            full_candidates,
            refresh_seed=refresh_seed,
            mode=mode,
            limit=1,
        )
        general_candidates = _load_employee_quiz_questions(
            db,
            permission_level=ContentLevel.GENERAL,
            visible_content_levels=user_visible_content_levels,
            user=user,
            limit=EMPLOYEE_QUIZ_CANDIDATE_WINDOW,
        )
        general_items = _sample_employee_quiz_questions(
            general_candidates,
            refresh_seed=refresh_seed,
            mode=mode,
            limit=9 if reserved_full else EMPLOYEE_QUIZ_LIMIT,
        )
        selected = reserved_full + general_items
        if reserved_full and len(selected) < EMPLOYEE_QUIZ_LIMIT:
            selected_ids = {question.id for question in selected}
            additional_full_candidates = [
                question for question in full_candidates if question.id not in selected_ids
            ]
            selected.extend(
                _sample_employee_quiz_questions(
                    additional_full_candidates,
                    refresh_seed=refresh_seed,
                    mode=mode,
                    limit=EMPLOYEE_QUIZ_LIMIT - len(selected),
                )
            )
        return selected

    reserved_full = _load_employee_quiz_questions(
        db,
        permission_level=ContentLevel.FULL,
        visible_content_levels=user_visible_content_levels,
        user=user,
        limit=1,
    )
    general_items = _load_employee_quiz_questions(
        db,
        permission_level=ContentLevel.GENERAL,
        visible_content_levels=user_visible_content_levels,
        user=user,
        limit=9 if reserved_full else EMPLOYEE_QUIZ_LIMIT,
    )
    selected = reserved_full + general_items
    if reserved_full and len(selected) < EMPLOYEE_QUIZ_LIMIT:
        selected.extend(
            _load_employee_quiz_questions(
                db,
                permission_level=ContentLevel.FULL,
                visible_content_levels=user_visible_content_levels,
                user=user,
                limit=EMPLOYEE_QUIZ_LIMIT - len(selected),
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
        .outerjoin(Content, QuizQuestion.related_content_id == Content.id)
        .options(joinedload(QuizQuestion.related_content))
        .where(QuizQuestion.id.in_(requested_ids))
        .where(QuizQuestion.status == QuestionStatus.ENABLED.value)
        .where(QuizQuestion.review_status == QuizReviewStatus.APPROVED.value)
        .where(QuizQuestion.needs_review.is_(False))
        .where(or_(QuizQuestion.expires_at.is_(None), QuizQuestion.expires_at > datetime.now(UTC)))
        .where(QuizQuestion.permission_level.in_(visible_levels_for(user)))
        .where(visible_related_content_filter(visible_levels_for(user), user))
    )
    questions = list(db.scalars(stmt).all())
    if len(questions) != len(requested_ids):
        raise AppError(code="not_found", message="Question not found.", status_code=404)
    return {question.id: question for question in questions}


def quiz_generation_batch_to_dict(batch: QuizGenerationBatch) -> dict[str, Any]:
    return {
        "id": batch.id,
        "content_id": batch.content_id,
        "version_id": batch.version_id,
        "update_level": batch.update_level,
        "status": batch.status,
        "model_name": batch.model_name,
        "prompt_version": batch.prompt_version,
        "requested_count": batch.requested_count,
        "generated_count": batch.generated_count,
        "created_by": batch.created_by,
        "created_at": batch.created_at,
        "error_message": batch.error_message,
    }


def quiz_set_to_dict(quiz_set: QuizSet) -> dict[str, Any]:
    return {
        "id": quiz_set.id,
        "title": quiz_set.title,
        "description": quiz_set.description,
        "related_content_id": quiz_set.related_content_id,
        "related_version_id": quiz_set.related_version_id,
        "update_level": quiz_set.update_level,
        "permission_level": quiz_set.permission_level,
        "status": quiz_set.status,
        "expires_at": quiz_set.expires_at,
        "created_at": quiz_set.created_at,
        "question_count": len(quiz_set.items),
    }


def list_quiz_generation_batches(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[QuizGenerationBatch], int]:
    stmt = select(QuizGenerationBatch)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(QuizGenerationBatch.created_at.desc(), QuizGenerationBatch.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total


def list_quiz_sets(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[QuizSet], int]:
    stmt = select(QuizSet).options(joinedload(QuizSet.items))
    total = db.scalar(select(func.count()).select_from(select(QuizSet).subquery())) or 0
    items = db.scalars(
        stmt.order_by(QuizSet.created_at.desc(), QuizSet.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).unique().all()
    return list(items), total


def quiz_generation_status_for_version(db: Session, version: ContentVersion) -> str:
    if default_requested_count_for_version(version) <= 0:
        return "not_required"
    latest = db.scalar(
        select(QuizGenerationBatch)
        .where(QuizGenerationBatch.version_id == version.id)
        .where(QuizGenerationBatch.prompt_version == QUIZ_GENERATION_PROMPT_VERSION)
        .order_by(QuizGenerationBatch.id.desc())
        .limit(1)
    )
    if latest is None:
        return "pending"
    if latest.status == QuizGenerationStatus.COMPLETED.value:
        return "completed"
    if latest.status == QuizGenerationStatus.FAILED.value:
        return "failed"
    return "pending"


def deactivate_quiz_sets_for_content(db: Session, *, content_id: int) -> None:
    quiz_sets = db.scalars(
        select(QuizSet)
        .where(QuizSet.related_content_id == content_id)
        .where(QuizSet.status == QuizSetStatus.ACTIVE.value)
    ).all()
    for quiz_set in quiz_sets:
        quiz_set.status = QuizSetStatus.INACTIVE.value


def deactivate_stale_quiz_sets_for_content(
    db: Session,
    *,
    content_id: int,
    current_version_id: int,
) -> None:
    quiz_sets = db.scalars(
        select(QuizSet)
        .where(QuizSet.related_content_id == content_id)
        .where(QuizSet.related_version_id != current_version_id)
        .where(QuizSet.status == QuizSetStatus.ACTIVE.value)
    ).all()
    for quiz_set in quiz_sets:
        quiz_set.status = QuizSetStatus.INACTIVE.value


def mark_question_source_invalid(question: QuizQuestion, *, reason: str) -> None:
    if question.review_status in {
        QuizReviewStatus.DRAFT.value,
        QuizReviewStatus.PENDING_REVIEW.value,
    }:
        question.review_status = QuizReviewStatus.REJECTED.value
        question.status = QuestionStatus.DISABLED.value
        question.needs_review = False
        question.review_reason = reason
        return

    if question.review_status == QuizReviewStatus.APPROVED.value:
        question.status = QuestionStatus.DISABLED.value
        question.needs_review = True
        question.review_reason = reason
        return

    question.status = QuestionStatus.DISABLED.value
    if not question.review_reason:
        question.review_reason = reason


def invalidate_quiz_questions_for_offline_content(db: Session, *, content_id: int) -> None:
    reason = "源内容已下线，关联候选题已自动驳回或禁用。"
    questions = db.scalars(
        select(QuizQuestion).where(QuizQuestion.related_content_id == content_id)
    ).all()
    for question in questions:
        mark_question_source_invalid(question, reason=reason)


def deactivate_quiz_assets_for_offline_content(db: Session, *, content_id: int) -> None:
    deactivate_quiz_sets_for_content(db, content_id=content_id)
    invalidate_quiz_questions_for_offline_content(db, content_id=content_id)


def default_requested_count_for_version(version: ContentVersion) -> int:
    if version.quiz_action == QuizAction.GENERATE_PACK.value:
        return 5
    if version.quiz_action == QuizAction.REVIEW_RELATED.value:
        return 3
    return 0


def question_priority_for_version(version: ContentVersion) -> int:
    if version.update_level == UpdateLevel.MAJOR.value or version.quiz_action == QuizAction.GENERATE_PACK.value:
        return MAJOR_TOPIC_PRIORITY
    if version.update_level == UpdateLevel.MEDIUM.value or version.quiz_action == QuizAction.REVIEW_RELATED.value:
        return MEDIUM_UPDATE_PRIORITY
    return 0


def chat_model_name(dashscope_client) -> str:
    settings = getattr(dashscope_client, "settings", None)
    if settings is not None and getattr(settings, "dashscope_chat_model", None):
        return settings.dashscope_chat_model
    return getattr(dashscope_client, "chat_model", "qwen-plus")


def quiz_model_name(dashscope_client) -> str:
    settings = getattr(dashscope_client, "settings", None)
    if settings is not None and getattr(settings, "dashscope_quiz_model", None):
        return settings.dashscope_quiz_model
    return chat_model_name(dashscope_client)


def quiz_timeout_seconds(dashscope_client) -> float | None:
    settings = getattr(dashscope_client, "settings", None)
    if settings is not None:
        return getattr(settings, "dashscope_quiz_timeout_seconds", None)
    return None


def version_context_text(content: Content, version: ContentVersion) -> str:
    payload_text = (
        json.dumps(version.structured_payload, ensure_ascii=False)
        if version.structured_payload
        else ""
    )
    parts = [
        f"标题：{version.title}",
        f"分类：{content.category or '-'}",
        f"摘要：{version.summary or '-'}",
        f"正文：{version.body}",
        f"结构化内容：{payload_text}" if payload_text else None,
    ]
    return "\n".join(part for part in parts if part)


def generation_prompt(version: ContentVersion, requested_count: int) -> str:
    return (
        "请基于提供的企业官方内容生成巩固测试候选题。"
        "只能使用来源中的信息，不得增加来源没有的事实、数字或业务结论。"
        f"请生成 {requested_count} 道单选题。"
        "每道题必须有 question、options、answer、explanation 四个字段，"
        "options 至少两个选项，answer 必须是选项之一。"
        "只输出 JSON，不要输出 Markdown，不要输出解释文字。"
        "JSON 结构必须为："
        '{"questions":[{"question":"题干","options":["选项A","选项B"],'
        '"answer":"选项A","explanation":"解析"}]}。'
        f"当前版本：v{version.version_no}，更新级别：{version.update_level}。"
    )


def decode_generated_questions(answer_text: str, *, requested_count: int) -> list[dict[str, Any]]:
    raw = answer_text.strip()
    if raw.startswith("```"):
        raw = "\n".join(line for line in raw.splitlines() if not line.strip().startswith("```")).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("AI quiz generation did not return JSON.") from None
        data = json.loads(raw[start : end + 1])

    items = data.get("questions") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("AI quiz generation JSON must contain a questions list.")

    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        raw_options = item.get("options")
        answer = str(item.get("answer") or item.get("correct_answer") or "").strip()
        explanation = str(item.get("explanation") or "").strip() or None
        if not question or not isinstance(raw_options, list) or len(raw_options) < 2 or not answer:
            continue
        options = [str(option).strip() for option in raw_options if str(option).strip()]
        if len(options) < 2:
            continue
        normalized.append(
            {
                "question": question,
                "options": options,
                "answer": answer,
                "explanation": explanation,
            }
        )
        if len(normalized) >= requested_count:
            break
    if not normalized:
        raise ValueError("AI quiz generation returned no valid quiz questions.")
    return normalized


def ensure_major_quiz_set(
    db: Session,
    *,
    content: Content,
    version: ContentVersion,
    questions: list[QuizQuestion],
) -> QuizSet:
    quiz_set = db.scalar(
        select(QuizSet).where(QuizSet.related_version_id == version.id).limit(1)
    )
    if quiz_set is None:
        quiz_set = QuizSet(
            title=f"{version.title} 专题测验",
            description=f"基于 v{version.version_no} 大更新自动创建的专题测验包。",
            related_content_id=content.id,
            related_version_id=version.id,
            update_level=version.update_level,
            permission_level=version.permission_level,
            status=QuizSetStatus.ACTIVE.value,
        )
        db.add(quiz_set)
        db.flush()

    existing_question_ids = {item.question_id for item in quiz_set.items}
    next_order = len(existing_question_ids) + 1
    for question in questions:
        if question.id in existing_question_ids:
            continue
        db.add(
            QuizQuestionSetItem(
                quiz_set_id=quiz_set.id,
                question_id=question.id,
                sort_order=next_order,
            )
        )
        next_order += 1
    return quiz_set


def generate_candidate_questions_for_version(
    db: Session,
    *,
    content: Content,
    version: ContentVersion,
    admin: User,
    dashscope_client,
    requested_count: int | None = None,
    create_quiz_set: bool = True,
) -> QuizGenerationBatch:
    resolved_count = requested_count or default_requested_count_for_version(version)
    if resolved_count <= 0:
        raise AppError(code="quiz_generation_not_required", message="该版本不需要生成候选题。", status_code=409)
    resolved_count = min(resolved_count, 10)

    batch = QuizGenerationBatch(
        content_id=content.id,
        version_id=version.id,
        update_level=version.update_level,
        status=QuizGenerationStatus.PENDING.value,
        model_name=quiz_model_name(dashscope_client),
        prompt_version=QUIZ_GENERATION_PROMPT_VERSION,
        requested_count=resolved_count,
        generated_count=0,
        created_by=admin.id,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    try:
        generation = dashscope_client.generate_answer(
            question=generation_prompt(version, resolved_count),
            contexts=[
                {
                    "source": {"title": version.title, "version_no": version.version_no},
                    "text": version_context_text(content, version),
                }
            ],
            model_name=quiz_model_name(dashscope_client),
            timeout_seconds=quiz_timeout_seconds(dashscope_client),
        )
        generated_payloads = decode_generated_questions(generation.answer_text, requested_count=resolved_count)
        priority = question_priority_for_version(version)
        generated_questions: list[QuizQuestion] = []
        for item in generated_payloads:
            question = QuizQuestion(
                question=item["question"],
                options=item["options"],
                answer=item["answer"],
                explanation=item["explanation"],
                related_content_id=content.id,
                related_version_id=version.id,
                permission_level=version.permission_level,
                status=QuestionStatus.DISABLED.value,
                source_type=QuizSourceType.AI_GENERATED.value,
                review_status=QuizReviewStatus.PENDING_REVIEW.value,
                generation_batch_id=batch.id,
                needs_review=False,
                priority=priority,
            )
            db.add(question)
            generated_questions.append(question)
        db.flush()

        if create_quiz_set and version.update_level == UpdateLevel.MAJOR.value:
            ensure_major_quiz_set(db, content=content, version=version, questions=generated_questions)

        batch.status = QuizGenerationStatus.COMPLETED.value
        batch.generated_count = len(generated_questions)
        db.commit()
        db.refresh(batch)
        return batch
    except Exception as exc:
        db.rollback()
        failed_batch = db.get(QuizGenerationBatch, batch.id)
        if failed_batch is None:
            raise
        provider_error = normalize_provider_error(exc)
        failed_batch.status = QuizGenerationStatus.FAILED.value
        failed_batch.error_message = provider_error.message
        failed_batch.generated_count = 0
        db.commit()
        db.refresh(failed_batch)
        return failed_batch


def maybe_generate_quiz_assets_after_publish(
    db: Session,
    *,
    content_id: int,
    version_id: int,
    admin: User,
    dashscope_client,
) -> QuizGenerationBatch | None:
    content = db.get(Content, content_id)
    version = db.get(ContentVersion, version_id)
    if content is None or version is None or version.content_id != content.id:
        return None
    if default_requested_count_for_version(version) <= 0:
        return None
    existing = db.scalar(
        select(QuizGenerationBatch)
        .where(QuizGenerationBatch.version_id == version.id)
        .where(QuizGenerationBatch.prompt_version == QUIZ_GENERATION_PROMPT_VERSION)
        .order_by(QuizGenerationBatch.id.desc())
        .limit(1)
    )
    if existing is not None and existing.status == QuizGenerationStatus.COMPLETED.value:
        return existing
    return generate_candidate_questions_for_version(
        db,
        content=content,
        version=version,
        admin=admin,
        dashscope_client=dashscope_client,
        create_quiz_set=version.update_level == UpdateLevel.MAJOR.value,
    )


def generate_candidate_questions_for_content_version(
    db: Session,
    *,
    content_id: int,
    version_id: int,
    admin: User,
    dashscope_client,
    requested_count: int | None = None,
    create_quiz_set: bool = True,
) -> QuizGenerationBatch:
    content = db.get(Content, content_id)
    version = db.get(ContentVersion, version_id)
    if content is None or version is None or version.content_id != content.id:
        raise AppError(code="not_found", message="内容版本不存在。", status_code=404)
    return generate_candidate_questions_for_version(
        db,
        content=content,
        version=version,
        admin=admin,
        dashscope_client=dashscope_client,
        requested_count=requested_count,
        create_quiz_set=create_quiz_set,
    )
