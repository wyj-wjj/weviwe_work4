"""add content draft fields

Revision ID: 0002_add_content_draft_fields
Revises: 0001_initial_schema
Create Date: 2026-06-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0002_add_content_draft_fields"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("contents", sa.Column("draft_summary", sa.Text(), nullable=True))
    op.add_column("contents", sa.Column("draft_body", sa.Text(), nullable=True))
    op.add_column("contents", sa.Column("draft_payload", sa.JSON(), nullable=True))
    op.execute("update contents set draft_body = title where draft_body is null")
    with op.batch_alter_table("contents") as batch_op:
        batch_op.alter_column("draft_body", existing_type=sa.Text(), nullable=False)


def downgrade() -> None:
    op.drop_column("contents", "draft_payload")
    op.drop_column("contents", "draft_body")
    op.drop_column("contents", "draft_summary")
