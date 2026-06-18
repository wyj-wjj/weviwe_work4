"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("account_type", sa.String(length=32), nullable=False),
        sa.Column("content_level", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("account_type in ('admin', 'full_user', 'general_user')", name="ck_users_account_type"),
        sa.CheckConstraint("content_level in ('general', 'full')", name="ck_users_content_level"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=False)

    op.create_table(
        "contents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("permission_level", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_version_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "content_type in ('base_script', 'standard_script', 'must_read')",
            name="ck_contents_content_type",
        ),
        sa.CheckConstraint("permission_level in ('general', 'full')", name="ck_contents_permission_level"),
        sa.CheckConstraint("status in ('draft', 'published', 'offline')", name="ck_contents_status"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "content_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("structured_payload", sa.JSON(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_id", "version_no", name="uq_content_versions_content_version_no"),
    )
    op.create_index(op.f("ix_content_versions_content_id"), "content_versions", ["content_id"], unique=False)

    op.create_table(
        "content_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("chunk_type", sa.String(length=64), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("permission_level", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"]),
        sa.ForeignKeyConstraint(["version_id"], ["content_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_content_chunks_content_id"), "content_chunks", ["content_id"], unique=False)
    op.create_index(op.f("ix_content_chunks_version_id"), "content_chunks", ["version_id"], unique=False)

    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("answer", sa.String(length=255), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("related_content_id", sa.Integer(), nullable=True),
        sa.Column("permission_level", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("permission_level in ('general', 'full')", name="ck_quiz_questions_permission_level"),
        sa.CheckConstraint("status in ('enabled', 'disabled')", name="ck_quiz_questions_status"),
        sa.ForeignKeyConstraint(["related_content_id"], ["contents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "missed_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("account_type", sa.String(length=32), nullable=False),
        sa.Column("content_level", sa.String(length=32), nullable=False),
        sa.Column("asked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("account_type in ('admin', 'full_user', 'general_user')", name="ck_missed_questions_account_type"),
        sa.CheckConstraint("content_level in ('general', 'full')", name="ck_missed_questions_content_level"),
        sa.CheckConstraint("status in ('new', 'handled')", name="ck_missed_questions_status"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "vector_index_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.Integer(), nullable=False),
        sa.Column("milvus_collection", sa.String(length=128), nullable=False),
        sa.Column("milvus_primary_key", sa.String(length=128), nullable=False),
        sa.Column("embedding_model", sa.String(length=128), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["content_chunks.id"]),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"]),
        sa.ForeignKeyConstraint(["version_id"], ["content_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_vector_index_records_chunk_id"), "vector_index_records", ["chunk_id"], unique=False)
    op.create_index(op.f("ix_vector_index_records_content_id"), "vector_index_records", ["content_id"], unique=False)
    op.create_index(op.f("ix_vector_index_records_version_id"), "vector_index_records", ["version_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_vector_index_records_version_id"), table_name="vector_index_records")
    op.drop_index(op.f("ix_vector_index_records_content_id"), table_name="vector_index_records")
    op.drop_index(op.f("ix_vector_index_records_chunk_id"), table_name="vector_index_records")
    op.drop_table("vector_index_records")
    op.drop_table("missed_questions")
    op.drop_table("quiz_questions")
    op.drop_index(op.f("ix_content_chunks_version_id"), table_name="content_chunks")
    op.drop_index(op.f("ix_content_chunks_content_id"), table_name="content_chunks")
    op.drop_table("content_chunks")
    op.drop_index(op.f("ix_content_versions_content_id"), table_name="content_versions")
    op.drop_table("content_versions")
    op.drop_table("contents")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")
