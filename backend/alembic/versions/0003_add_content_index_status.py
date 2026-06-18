"""add content index status

Revision ID: 0003_add_content_index_status
Revises: 0002_add_content_draft_fields
Create Date: 2026-06-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0003_add_content_index_status"
down_revision: str | None = "0002_add_content_draft_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "contents",
        sa.Column(
            "index_status",
            sa.String(length=32),
            nullable=False,
            server_default="not_synced",
        ),
    )
    if op.get_bind().dialect.name != "sqlite":
        op.create_check_constraint(
            "ck_contents_index_status",
            "contents",
            "index_status in ('not_synced', 'synced', 'failed')",
        )
    with op.batch_alter_table("contents") as batch_op:
        batch_op.alter_column("index_status", existing_type=sa.String(length=32), server_default=None)


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("ck_contents_index_status", "contents", type_="check")
    op.drop_column("contents", "index_status")
