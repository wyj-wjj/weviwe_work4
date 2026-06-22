from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import ContentLevel, ContentStatus, ContentType, IndexStatus
from app.models.base import Base, TimestampMixin, utc_now


class Content(TimestampMixin, Base):
    __tablename__ = "contents"
    __table_args__ = (
        CheckConstraint(
            f"content_type in {tuple(item.value for item in ContentType)}",
            name="ck_contents_content_type",
        ),
        CheckConstraint(
            f"permission_level in {tuple(item.value for item in ContentLevel)}",
            name="ck_contents_permission_level",
        ),
        CheckConstraint(
            f"status in {tuple(item.value for item in ContentStatus)}",
            name="ck_contents_status",
        ),
        CheckConstraint(
            f"index_status in {tuple(item.value for item in IndexStatus)}",
            name="ck_contents_index_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(128))
    permission_level: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ContentStatus.DRAFT.value)
    index_status: Mapped[str] = mapped_column(String(32), nullable=False, default=IndexStatus.NOT_SYNCED.value)
    draft_summary: Mapped[str | None] = mapped_column(Text)
    draft_body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    draft_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    draft_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    published_draft_revision: Mapped[int | None] = mapped_column(Integer)
    current_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_versions.id", use_alter=True, name="fk_contents_current_version_id"),
        nullable=True,
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    creator = relationship("User", back_populates="created_contents", foreign_keys=[created_by])
    versions = relationship("ContentVersion", back_populates="content", foreign_keys="ContentVersion.content_id")
    current_version = relationship(
        "ContentVersion",
        primaryjoin="Content.current_version_id == ContentVersion.id",
        foreign_keys=[current_version_id],
        uselist=False,
        post_update=True,
    )
    chunks = relationship("ContentChunk", back_populates="content")
    vector_index_records = relationship("VectorIndexRecord", back_populates="content")


class ContentVersion(Base):
    __tablename__ = "content_versions"
    __table_args__ = (UniqueConstraint("content_id", "version_no", name="uq_content_versions_content_version_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    structured_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    permission_level: Mapped[str] = mapped_column(String(32), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    content = relationship("Content", back_populates="versions", foreign_keys=[content_id])
    creator = relationship("User", back_populates="created_versions", foreign_keys=[created_by])
    chunks = relationship("ContentChunk", back_populates="version")
    vector_index_records = relationship("VectorIndexRecord", back_populates="version")


@event.listens_for(ContentVersion, "before_insert")
def snapshot_content_version_permission(_mapper, _connection, version: ContentVersion) -> None:
    if not version.permission_level and version.content is not None:
        version.permission_level = version.content.permission_level


class ContentChunk(TimestampMixin, Base):
    __tablename__ = "content_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"), nullable=False, index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("content_versions.id"), nullable=False, index=True)
    chunk_type: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    token_estimate: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    permission_level: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    content = relationship("Content", back_populates="chunks")
    version = relationship("ContentVersion", back_populates="chunks")
    vector_index_records = relationship("VectorIndexRecord", back_populates="chunk")


class VectorIndexRecord(Base):
    __tablename__ = "vector_index_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"), nullable=False, index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("content_versions.id"), nullable=False, index=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("content_chunks.id"), nullable=False, index=True)
    milvus_collection: Mapped[str] = mapped_column(String(128), nullable=False)
    milvus_primary_key: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    content = relationship("Content", back_populates="vector_index_records")
    version = relationship("ContentVersion", back_populates="vector_index_records")
    chunk = relationship("ContentChunk", back_populates="vector_index_records")
