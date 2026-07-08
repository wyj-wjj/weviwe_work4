from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domain.enums import ContentScope, ContentStatus, ContentType, IndexStatus, QuizAction, UpdateLevel
from app.models.content import Content, ContentChunk, ContentVersion
from app.models.user import User
from app.services.department_service import ensure_active_department
from app.services.permission_service import scope_filter, visible_levels_for


def not_found(message: str = "资源不存在。") -> AppError:
    return AppError(code="not_found", message=message, status_code=404)


def content_to_admin_dict(content: Content) -> dict[str, Any]:
    current_version_no = content.current_version.version_no if content.current_version else None
    current_update_level = content.current_version.update_level if content.current_version else None
    return {
        "id": content.id,
        "content_type": content.content_type,
        "title": content.title,
        "category": content.category,
        "permission_level": content.permission_level,
        "scope_type": content.scope_type,
        "department_id": content.department_id,
        "department_name": content.department.name if content.department else None,
        "status": content.status,
        "current_version_id": content.current_version_id,
        "current_version_no": current_version_no,
        "current_update_level": current_update_level,
        "index_status": content.index_status,
        "summary": content.draft_summary,
        "body": content.draft_body,
        "structured_payload": content.draft_payload,
    }


def validate_content_scope(db: Session, *, scope_type: str, department_id: int | None) -> None:
    if scope_type == ContentScope.GLOBAL.value:
        if department_id is not None:
            raise AppError(code="invalid_content_scope", message="全公司通用内容不能设置部门。", status_code=422)
        return
    if scope_type != ContentScope.DEPARTMENT.value:
        raise AppError(code="invalid_content_scope", message="内容可见范围不合法。", status_code=422)
    if department_id is None:
        raise AppError(code="invalid_content_scope", message="限定部门内容必须选择部门。", status_code=422)
    ensure_active_department(db, department_id)


def create_content(db: Session, *, creator: User, payload: Any) -> Content:
    scope_type = payload.scope_type.value
    department_id = payload.department_id
    validate_content_scope(db, scope_type=scope_type, department_id=department_id)
    content = Content(
        content_type=payload.content_type.value,
        title=payload.title,
        category=payload.category,
        permission_level=payload.permission_level.value,
        scope_type=scope_type,
        department_id=department_id,
        status=ContentStatus.DRAFT.value,
        index_status=IndexStatus.NOT_SYNCED.value,
        draft_summary=payload.summary,
        draft_body=payload.body,
        draft_payload=payload.structured_payload,
        creator=creator,
    )
    db.add(content)
    db.commit()
    db.refresh(content)
    return content


def get_content_or_404(db: Session, content_id: int) -> Content:
    content = db.get(Content, content_id)
    if content is None:
        raise not_found("内容不存在。")
    return content


def update_content(db: Session, *, content_id: int, payload: Any) -> Content:
    content = get_content_or_404(db, content_id)
    if content.status == ContentStatus.OFFLINE.value:
        raise AppError(code="content_offline", message="已下线内容不可编辑。", status_code=409)
    updates = payload.model_dump(exclude_unset=True)
    stored_updates: dict[str, Any] = {}
    if "title" in updates and updates["title"] is not None:
        stored_updates["title"] = updates["title"]
    if "category" in updates:
        stored_updates["category"] = updates["category"]
    if "permission_level" in updates and updates["permission_level"] is not None:
        stored_updates["permission_level"] = updates["permission_level"].value
    if "scope_type" in updates or "department_id" in updates:
        next_scope_type = enum_value(updates.get("scope_type")) or content.scope_type
        next_department_id = updates["department_id"] if "department_id" in updates else content.department_id
        if next_scope_type == ContentScope.GLOBAL.value and "department_id" not in updates:
            next_department_id = None
        validate_content_scope(db, scope_type=next_scope_type, department_id=next_department_id)
        stored_updates["scope_type"] = next_scope_type
        stored_updates["department_id"] = next_department_id
    if "summary" in updates:
        stored_updates["draft_summary"] = updates["summary"]
    if "body" in updates and updates["body"] is not None:
        stored_updates["draft_body"] = updates["body"]
    if "structured_payload" in updates:
        stored_updates["draft_payload"] = updates["structured_payload"]

    changed = False
    for field, value in stored_updates.items():
        if getattr(content, field) != value:
            setattr(content, field, value)
            changed = True
    if changed:
        content.draft_revision += 1
    db.commit()
    db.refresh(content)
    return content


def list_admin_contents(
    db: Session,
    *,
    content_type: str | None = None,
    status: str | None = None,
    permission_level: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Content], int]:
    stmt: Select[tuple[Content]] = select(Content)
    if content_type:
        stmt = stmt.where(Content.content_type == content_type)
    if status:
        stmt = stmt.where(Content.status == status)
    if permission_level:
        stmt = stmt.where(Content.permission_level == permission_level)
    if category:
        stmt = stmt.where(Content.category == category)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(Content.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return list(items), total


def list_content_categories(db: Session, *, limit: int = 100) -> list[str]:
    categories: list[str] = []
    seen: set[str] = set()
    raw_categories = db.scalars(
        select(Content.category)
        .where(Content.category.is_not(None))
        .order_by(Content.updated_at.desc(), Content.id.desc())
        .limit(limit * 5)
    ).all()
    for raw_category in raw_categories:
        category = (raw_category or "").strip()
        if not category or category in seen:
            continue
        seen.add(category)
        categories.append(category)
        if len(categories) >= limit:
            break
    return categories


def list_content_scenes(db: Session, *, limit: int = 100) -> list[str]:
    scenes: list[str] = []
    seen: set[str] = set()
    contents = db.scalars(
        select(Content)
        .where(Content.content_type == ContentType.STANDARD_SCRIPT.value)
        .order_by(Content.updated_at.desc(), Content.id.desc())
        .limit(limit * 5)
    ).all()
    for content in contents:
        payloads = [content.draft_payload]
        if content.current_version is not None:
            payloads.append(content.current_version.structured_payload)
        for payload in payloads:
            if not isinstance(payload, dict):
                continue
            scene = str(payload.get("scene") or "").strip()
            if not scene or scene in seen:
                continue
            seen.add(scene)
            scenes.append(scene)
            if len(scenes) >= limit:
                return scenes
    return scenes


def delete_draft_content(db: Session, *, content_id: int) -> None:
    content = get_content_or_404(db, content_id)
    if content.status != ContentStatus.DRAFT.value or content.current_version_id is not None:
        raise AppError(code="draft_delete_forbidden", message="只能删除未发布草稿。", status_code=409)
    db.delete(content)
    db.commit()


def next_version_no(content: Content) -> int:
    if not content.versions:
        return 1
    return max(version.version_no for version in content.versions) + 1


def enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def default_quiz_action_for(update_level: str) -> str:
    if update_level == UpdateLevel.MINOR.value:
        return QuizAction.NONE.value
    if update_level == UpdateLevel.MEDIUM.value:
        return QuizAction.REVIEW_RELATED.value
    return QuizAction.GENERATE_PACK.value


def mark_related_quiz_questions_for_review(
    db: Session,
    *,
    content: Content,
    update_level: str,
    version: ContentVersion,
) -> None:
    from app.models.quiz import QuizQuestion
    from app.domain.enums import QuestionStatus, QuizReviewStatus
    from app.services.quiz_service import mark_question_source_invalid

    should_mark_current_review = update_level in {UpdateLevel.MEDIUM.value, UpdateLevel.MAJOR.value}
    review_reason = f"{update_level} update published as v{version.version_no}; related quiz question requires review."
    stale_reason = f"源版本已被 v{version.version_no} 替代，旧版本候选题已失效。"
    questions = db.scalars(
        select(QuizQuestion).where(QuizQuestion.related_content_id == content.id)
    ).all()
    for question in questions:
        if question.related_version_id is not None and question.related_version_id != version.id:
            if update_level != UpdateLevel.MINOR.value:
                mark_question_source_invalid(question, reason=stale_reason)
            continue
        if not should_mark_current_review:
            continue
        if (
            question.review_status == QuizReviewStatus.APPROVED.value
            and question.status == QuestionStatus.ENABLED.value
        ):
            question.status = QuestionStatus.DISABLED.value
        question.needs_review = True
        question.review_reason = review_reason


def publish_content(
    db: Session,
    *,
    content_id: int,
    update_level: UpdateLevel | str = UpdateLevel.MAJOR,
    change_summary: str | None = None,
    quiz_action: QuizAction | str | None = None,
    ai_suggested_update_level: UpdateLevel | str | None = None,
    ai_suggestion_reason: str | None = None,
) -> ContentVersion:
    update_level_value = enum_value(update_level) or UpdateLevel.MAJOR.value
    quiz_action_value = enum_value(quiz_action) or default_quiz_action_for(update_level_value)
    ai_suggested_update_level_value = enum_value(ai_suggested_update_level)

    content = db.scalar(
        select(Content)
        .where(Content.id == content_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if content is None:
        raise not_found("内容不存在。")
    if content.status == ContentStatus.OFFLINE.value:
        raise AppError(code="content_offline", message="已下线内容不可发布。", status_code=409)
    if (
        content.current_version_id is not None
        and content.published_draft_revision == content.draft_revision
    ):
        current_version = db.get(ContentVersion, content.current_version_id)
        if current_version is None:
            raise not_found("当前版本不存在。")
        db.commit()
        return current_version

    now = datetime.now(UTC)
    for chunk in content.chunks:
        chunk.is_active = False
    for record in content.vector_index_records:
        record.is_active = False

    version = ContentVersion(
        content=content,
        version_no=next_version_no(content),
        title=content.title,
        summary=content.draft_summary,
        body=content.draft_body,
        structured_payload=content.draft_payload,
        permission_level=content.permission_level,
        scope_type=content.scope_type,
        department_id=content.department_id,
        update_level=update_level_value,
        change_summary=change_summary,
        quiz_action=quiz_action_value,
        ai_suggested_update_level=ai_suggested_update_level_value,
        ai_suggestion_reason=ai_suggestion_reason,
        published_at=now,
        effective_at=now,
        created_by=content.created_by,
    )
    db.add(version)
    db.flush()
    content.status = ContentStatus.PUBLISHED.value
    content.index_status = IndexStatus.NOT_SYNCED.value
    content.current_version = version
    content.published_draft_revision = content.draft_revision
    mark_related_quiz_questions_for_review(
        db,
        content=content,
        update_level=update_level_value,
        version=version,
    )

    from app.services.quiz_service import deactivate_stale_quiz_sets_for_content

    deactivate_stale_quiz_sets_for_content(
        db,
        content_id=content.id,
        current_version_id=version.id,
        update_level=update_level_value,
    )

    from app.services.rag_index_service import replace_chunks_for_version

    replace_chunks_for_version(db, content=content, version=version)
    db.commit()
    db.refresh(version)
    return version


def offline_content(db: Session, *, content_id: int) -> Content:
    content = get_content_or_404(db, content_id)
    content.status = ContentStatus.OFFLINE.value
    content.index_status = IndexStatus.NOT_SYNCED.value
    for chunk in content.chunks:
        chunk.is_active = False
    for record in content.vector_index_records:
        record.is_active = False

    from app.services.quiz_service import deactivate_quiz_assets_for_offline_content

    deactivate_quiz_assets_for_offline_content(db, content_id=content.id)
    db.commit()
    db.refresh(content)
    return content


def list_versions(db: Session, *, content_id: int) -> list[ContentVersion]:
    content = get_content_or_404(db, content_id)
    return sorted(content.versions, key=lambda version: version.version_no, reverse=True)


def list_ai_searchable_chunks(db: Session) -> list[ContentChunk]:
    stmt = (
        select(ContentChunk)
        .join(Content)
        .where(Content.status == ContentStatus.PUBLISHED.value)
        .where(ContentChunk.is_active.is_(True))
        .where(Content.current_version_id == ContentChunk.version_id)
    )
    return list(db.scalars(stmt).all())


def employee_content_query(user: User) -> Select[tuple[Content]]:
    return (
        select(Content)
        .join(ContentVersion, Content.current_version_id == ContentVersion.id)
        .where(Content.status == ContentStatus.PUBLISHED.value)
        .where(Content.permission_level.in_(visible_levels_for(user)))
        .where(scope_filter(user, Content))
    )


def version_payload(content: Content) -> ContentVersion:
    if content.current_version is None:
        raise not_found("当前版本不存在。")
    return content.current_version
