from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.domain.enums import ContentStatus, ContentType, IndexStatus
from app.integrations.dashscope import normalize_provider_error
from app.integrations.milvus import MilvusVector
from app.models.content import Content, ContentChunk, ContentVersion, VectorIndexRecord


@dataclass(frozen=True)
class ChunkSpec:
    chunk_type: str
    text: str
    sort_order: int


@dataclass(frozen=True)
class IndexSyncResult:
    status: str
    indexed_count: int = 0
    error_code: str | None = None


def stable_content_hash(text: str) -> str:
    normalized = "\n".join(line.rstrip() for line in text.strip().splitlines())
    return sha256(normalized.encode("utf-8")).hexdigest()


def text_field(label: str, value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        rendered = "\n".join(str(item).strip() for item in value if str(item).strip())
    else:
        rendered = str(value).strip()
    return f"{label}：{rendered}" if rendered else None


def common_chunk_fields(content: Content, version: ContentVersion) -> list[str]:
    return [
        field
        for field in [
            text_field("标题", version.title),
            text_field("分类", content.category),
            text_field("摘要", version.summary),
        ]
        if field
    ]


def build_chunk_specs(content: Content, version: ContentVersion) -> list[ChunkSpec]:
    payload: dict[str, Any] = version.structured_payload or {}
    common_fields = common_chunk_fields(content, version)
    if content.content_type == ContentType.STANDARD_SCRIPT.value:
        items = payload.get("items")
        if isinstance(items, list) and items:
            specs = []
            for index, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    continue
                item_fields = [
                    field
                    for field in [
                        text_field("场景", item.get("scene")),
                        text_field("推荐说法", item.get("recommended_speech")),
                        text_field("禁用说法", item.get("forbidden_speech")),
                        text_field("注意事项", item.get("notes")),
                    ]
                    if field
                ]
                if item_fields:
                    specs.append(
                        ChunkSpec(
                            chunk_type="standard_script_scene",
                            text="\n".join([*common_fields, *item_fields]),
                            sort_order=index,
                        )
                    )
            if specs:
                return specs
        item_fields = [
            field
            for field in [
                text_field("场景", payload.get("scene")),
                text_field("推荐说法", payload.get("recommended_speech")),
                text_field("禁用说法", payload.get("forbidden_speech")),
                text_field("注意事项", payload.get("notes")),
            ]
            if field
        ]
        if not item_fields:
            fallback_body = text_field("正文", version.body)
            item_fields = [fallback_body] if fallback_body else []
        return [
            ChunkSpec(
                chunk_type="standard_script_scene",
                text="\n".join([*common_fields, *item_fields]),
                sort_order=1,
            )
        ]

    if content.content_type == ContentType.MUST_READ.value:
        update_body = payload.get("update_body") or version.body
        points = payload.get("adjustment_points") or []
        must_read_fields = [
            field
            for field in [
                text_field("更新正文", update_body),
                text_field("调整要点", points),
            ]
            if field
        ]
        return [
            ChunkSpec(
                chunk_type="must_read_update",
                text="\n".join([*common_fields, *must_read_fields]),
                sort_order=1,
            )
        ]

    base_fields = [
        field
        for field in [
            text_field("正文", version.body),
            text_field("要点", payload.get("points")),
        ]
        if field
    ]
    return [
        ChunkSpec(
            chunk_type="base_script_body",
            text="\n".join([*common_fields, *base_fields]),
            sort_order=1,
        )
    ]


def replace_chunks_for_version(db: Session, *, content: Content, version: ContentVersion) -> list[ContentChunk]:
    for chunk in content.chunks:
        chunk.is_active = False

    chunks: list[ContentChunk] = []
    for spec in build_chunk_specs(content, version):
        chunk = ContentChunk(
            content=content,
            version=version,
            chunk_type=spec.chunk_type,
            chunk_text=spec.text,
            sort_order=spec.sort_order,
            token_estimate=max(1, len(spec.text) // 2),
            content_hash=stable_content_hash(spec.text),
            permission_level=content.permission_level,
            is_active=True,
        )
        db.add(chunk)
        chunks.append(chunk)
    return chunks


def active_current_chunks(db: Session, *, content_id: int) -> list[ContentChunk]:
    stmt = (
        select(ContentChunk)
        .join(Content, Content.id == ContentChunk.content_id)
        .where(Content.id == content_id)
        .where(Content.status == ContentStatus.PUBLISHED.value)
        .where(Content.current_version_id == ContentChunk.version_id)
        .where(ContentChunk.is_active.is_(True))
        .order_by(ContentChunk.sort_order.asc(), ContentChunk.id.asc())
    )
    return list(db.scalars(stmt).all())


def sync_content_index(
    db: Session,
    *,
    content_id: int,
    dashscope_client,
    milvus_client,
    settings: Settings | None = None,
) -> IndexSyncResult:
    resolved_settings = settings or Settings()
    content = db.get(Content, content_id)
    if content is None:
        raise AppError(code="not_found", message="Content not found.", status_code=404)
    if content.status != ContentStatus.PUBLISHED.value or content.current_version_id is None:
        raise AppError(code="content_not_published", message="Only published content can be indexed.", status_code=409)

    chunks = active_current_chunks(db, content_id=content_id)
    try:
        vectors: list[MilvusVector] = []
        embeddings = []
        for chunk in chunks:
            embedding = dashscope_client.embed_text(chunk.chunk_text)
            embeddings.append((chunk, embedding))
        dimension = len(embeddings[0][1].vector) if embeddings else 0
        milvus_client.ensure_collection(resolved_settings.milvus_collection_name, dimension=dimension)

        for record in content.vector_index_records:
            record.is_active = False
        milvus_client.deactivate_by_content(resolved_settings.milvus_collection_name, content_id=content.id)

        for chunk, embedding in embeddings:
            primary_key = f"content-{content.id}-version-{chunk.version_id}-chunk-{chunk.id}"
            metadata = {
                "content_id": content.id,
                "version_id": chunk.version_id,
                "chunk_id": chunk.id,
                "permission_level": chunk.permission_level,
                "content_status": content.status,
                "is_active": True,
                "effective_at": content.current_version.effective_at.isoformat() if content.current_version and content.current_version.effective_at else None,
                "expired_at": content.current_version.expired_at.isoformat() if content.current_version and content.current_version.expired_at else None,
            }
            vectors.append(MilvusVector(primary_key=primary_key, vector=embedding.vector, metadata=metadata))
            db.add(
                VectorIndexRecord(
                    content=content,
                    version=chunk.version,
                    chunk=chunk,
                    milvus_collection=resolved_settings.milvus_collection_name,
                    milvus_primary_key=primary_key,
                    embedding_model=embedding.model,
                    embedding_dimension=len(embedding.vector),
                    content_hash=chunk.content_hash,
                    indexed_at=datetime.now(UTC),
                    is_active=True,
                )
            )
        milvus_client.upsert_vectors(resolved_settings.milvus_collection_name, vectors)
        content.index_status = IndexStatus.SYNCED.value
        db.commit()
        db.refresh(content)
        return IndexSyncResult(status=IndexStatus.SYNCED.value, indexed_count=len(vectors))
    except Exception as exc:
        db.rollback()
        failed_content = db.get(Content, content_id)
        if failed_content is not None:
            failed_content.index_status = IndexStatus.FAILED.value
            db.commit()
        provider_error = normalize_provider_error(exc)
        return IndexSyncResult(status=IndexStatus.FAILED.value, error_code=provider_error.code)
