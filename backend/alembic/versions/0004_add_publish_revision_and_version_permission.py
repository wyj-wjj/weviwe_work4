"""add publish revision and version permission

Revision ID: 0004_publish_revision_permission
Revises: 0003_add_content_index_status
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0004_publish_revision_permission"
down_revision: str | None = "0003_add_content_index_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "contents",
        sa.Column("draft_revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "contents",
        sa.Column("published_draft_revision", sa.Integer(), nullable=True),
    )
    op.add_column(
        "content_versions",
        sa.Column("permission_level", sa.String(length=32), nullable=True),
    )

    op.execute(
        """
        update content_versions
        set permission_level = (
            select contents.permission_level
            from contents
            where contents.id = content_versions.content_id
        )
        """
    )
    with op.batch_alter_table("content_versions") as batch_op:
        batch_op.alter_column(
            "permission_level",
            existing_type=sa.String(length=32),
            nullable=False,
        )

    op.execute(
        """
        update contents
        set published_draft_revision = draft_revision
        where current_version_id is not null
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("content_versions") as batch_op:
        batch_op.drop_column("permission_level")
    with op.batch_alter_table("contents") as batch_op:
        batch_op.drop_column("published_draft_revision")
        batch_op.drop_column("draft_revision")
