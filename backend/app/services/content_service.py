from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domain.enums import ContentLevel, ContentStatus, ContentType, IndexStatus
from app.models.content import Content, ContentChunk, ContentVersion
from app.models.user import User


def not_found(message: str = "资源不存在。") -> AppError:
    return AppError(code="not_found", message=message, status_code=404)


def content_to_admin_dict(content: Content) -> dict[str, Any]:
    current_version_no = content.current_version.version_no if content.current_version else None
    return {
        "id": content.id,
        "content_type": content.content_type,
        "title": content.title,
        "category": content.category,
        "permission_level": content.permission_level,
        "status": content.status,
        "current_version_id": content.current_version_id,
        "current_version_no": current_version_no,
        "index_status": content.index_status,
        "summary": content.draft_summary,
        "body": content.draft_body,
        "structured_payload": content.draft_payload,
    }


def create_content(db: Session, *, creator: User, payload: Any) -> Content:
    content = Content(
        content_type=payload.content_type.value,
        title=payload.title,
        category=payload.category,
        permission_level=payload.permission_level.value,
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


def next_version_no(content: Content) -> int:
    if not content.versions:
        return 1
    return max(version.version_no for version in content.versions) + 1


def publish_content(db: Session, *, content_id: int) -> ContentVersion:
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


def visible_levels_for(user: User) -> set[str]:
    if user.account_type in {"admin", "full_user"}:
        return {ContentLevel.GENERAL.value, ContentLevel.FULL.value}
    return {ContentLevel.GENERAL.value}


def employee_content_query(user: User) -> Select[tuple[Content]]:
    return (
        select(Content)
        .join(ContentVersion, Content.current_version_id == ContentVersion.id)
        .where(Content.status == ContentStatus.PUBLISHED.value)
        .where(Content.permission_level.in_(visible_levels_for(user)))
    )


def version_payload(content: Content) -> ContentVersion:
    if content.current_version is None:
        raise not_found("当前版本不存在。")
    return content.current_version
