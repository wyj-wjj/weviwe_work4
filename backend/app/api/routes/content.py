from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import ensure_content_visible, get_current_user, get_dashscope_client, get_milvus_client, require_admin
from app.core.errors import AppError
from app.db.session import get_db
from app.domain.enums import ContentStatus, ContentType
from app.models.content import Content, ContentVersion
from app.models.user import User
from app.schemas.content import ContentCreate, ContentUpdate
from app.services.content_service import (
    content_to_admin_dict,
    create_content,
    employee_content_query,
    get_content_or_404,
    list_admin_contents,
    list_versions,
    offline_content,
    publish_content,
    update_content,
    version_payload,
)
from app.services.rag_index_service import sync_content_index


router = APIRouter(tags=["content"])


def content_summary(content: Content) -> dict[str, Any]:
    return content_to_admin_dict(content)


@router.post("/api/admin/contents", status_code=201)
def admin_create_content(
    payload: ContentCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    content = create_content(db, creator=admin, payload=payload)
    return content_summary(content)


@router.get("/api/admin/contents")
def admin_list_contents(
    content_type: str | None = None,
    status: str | None = None,
    permission_level: str | None = None,
    category: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    items, total = list_admin_contents(
        db,
        content_type=content_type,
        status=status,
        permission_level=permission_level,
        category=category,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [content_summary(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/api/admin/contents/{content_id}")
def admin_get_content(
    content_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return content_summary(get_content_or_404(db, content_id))


@router.patch("/api/admin/contents/{content_id}")
def admin_update_content(
    content_id: int,
    payload: ContentUpdate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return content_summary(update_content(db, content_id=content_id, payload=payload))


@router.post("/api/admin/contents/{content_id}/publish")
def admin_publish_content(
    content_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    dashscope_client=Depends(get_dashscope_client),
    milvus_client=Depends(get_milvus_client),
) -> dict[str, Any]:
    publish_content(db, content_id=content_id)
    sync_content_index(db, content_id=content_id, dashscope_client=dashscope_client, milvus_client=milvus_client)
    return content_summary(get_content_or_404(db, content_id))


@router.post("/api/admin/contents/{content_id}/retry-index")
def admin_retry_content_index(
    content_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    dashscope_client=Depends(get_dashscope_client),
    milvus_client=Depends(get_milvus_client),
) -> dict[str, Any]:
    sync_content_index(db, content_id=content_id, dashscope_client=dashscope_client, milvus_client=milvus_client)
    return content_summary(get_content_or_404(db, content_id))


@router.post("/api/admin/contents/{content_id}/offline")
def admin_offline_content(
    content_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return content_summary(offline_content(db, content_id=content_id))


@router.get("/api/admin/contents/{content_id}/versions")
def admin_list_versions(
    content_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    versions = list_versions(db, content_id=content_id)
    return {
        "items": [
            {
                "id": version.id,
                "version_no": version.version_no,
                "title": version.title,
                "summary": version.summary,
                "body": version.body,
                "structured_payload": version.structured_payload,
                "published_at": version.published_at,
                "effective_at": version.effective_at,
                "expired_at": version.expired_at,
                "created_by": version.created_by,
            }
            for version in versions
        ]
    }


def must_read_item(content: Content) -> dict[str, Any]:
    version = version_payload(content)
    payload = version.structured_payload or {}
    return {
        "id": content.id,
        "title": version.title,
        "published_at": version.published_at,
        "effective_at": version.effective_at,
        "permission_level": content.permission_level,
        "update_body": payload.get("update_body", version.body),
        "adjustment_points": payload.get("adjustment_points", []),
    }


@router.get("/api/app/must-reads")
def app_list_must_reads(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stmt = (
        employee_content_query(current_user)
        .where(Content.content_type == ContentType.MUST_READ.value)
        .order_by(ContentVersion.published_at.desc(), Content.id.desc())
    )
    items = db.scalars(stmt).all()
    return {"items": [must_read_item(item) for item in items]}


@router.get("/api/app/must-reads/{content_id}")
def app_get_must_read(
    content_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    content = get_content_or_404(db, content_id)
    if content.status != ContentStatus.PUBLISHED.value or content.content_type != ContentType.MUST_READ.value:
        raise AppError(code="not_found", message="Content not found.", status_code=404)
    ensure_content_visible(current_user, content.permission_level)
    return must_read_item(content)


def script_item(content: Content) -> dict[str, Any]:
    version = version_payload(content)
    payload = version.structured_payload or {}
    if content.content_type == ContentType.STANDARD_SCRIPT.value:
        return {
            "id": content.id,
            "content_type": content.content_type,
            "title": version.title,
            "category": content.category,
            "permission_level": content.permission_level,
            "updated_at": version.published_at,
            "scene": payload.get("scene"),
            "recommended_speech_summary": (payload.get("recommended_speech") or version.body)[:80],
        }
    return {
        "id": content.id,
        "content_type": content.content_type,
        "title": version.title,
        "category": content.category,
        "permission_level": content.permission_level,
        "updated_at": version.published_at,
        "summary_points": (payload.get("points") or [])[:5],
    }


@router.get("/api/app/scripts")
def app_list_scripts(
    category: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stmt = employee_content_query(current_user).where(
        Content.content_type.in_([ContentType.BASE_SCRIPT.value, ContentType.STANDARD_SCRIPT.value])
    )
    if category:
        stmt = stmt.where(Content.category == category)
    items = db.scalars(stmt.order_by(Content.updated_at.desc(), Content.id.desc())).all()
    return {
        "base_scripts": [script_item(item) for item in items if item.content_type == ContentType.BASE_SCRIPT.value],
        "standard_scripts": [script_item(item) for item in items if item.content_type == ContentType.STANDARD_SCRIPT.value],
    }


@router.get("/api/app/scripts/{content_id}")
def app_get_script(
    content_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    content = get_content_or_404(db, content_id)
    if content.status != ContentStatus.PUBLISHED.value or content.content_type not in {
        ContentType.BASE_SCRIPT.value,
        ContentType.STANDARD_SCRIPT.value,
    }:
        raise AppError(code="not_found", message="Content not found.", status_code=404)
    ensure_content_visible(current_user, content.permission_level)
    version = version_payload(content)
    payload = version.structured_payload or {}
    if content.content_type == ContentType.STANDARD_SCRIPT.value:
        copy_text = "\n".join(
            part
            for part in [
                payload.get("scene"),
                payload.get("recommended_speech"),
                payload.get("forbidden_speech"),
                payload.get("notes"),
            ]
            if part
        )
        return {
            "id": content.id,
            "title": version.title,
            "content_type": content.content_type,
            "category": content.category,
            "permission_level": content.permission_level,
            "scene": payload.get("scene"),
            "recommended_speech": payload.get("recommended_speech"),
            "forbidden_speech": payload.get("forbidden_speech"),
            "notes": payload.get("notes"),
            "updated_at": version.published_at,
            "copy_text": copy_text,
        }
    return {
        "id": content.id,
        "title": version.title,
        "content_type": content.content_type,
        "category": content.category,
        "permission_level": content.permission_level,
        "body": version.body,
        "summary_points": payload.get("points", []),
        "updated_at": version.published_at,
        "copy_text": version.body,
    }
