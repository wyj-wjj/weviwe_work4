"""add quiz update policy fields

Revision ID: 0005_quiz_update_policy
Revises: 0004_publish_revision_permission
Create Date: 2026-06-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0005_quiz_update_policy"
down_revision: str | None = "0004_publish_revision_permission"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("content_versions") as batch_op:
        batch_op.add_column(
            sa.Column("update_level", sa.String(length=32), nullable=False, server_default="major"),
        )
        batch_op.add_column(sa.Column("change_summary", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("quiz_action", sa.String(length=32), nullable=False, server_default="none"),
        )
        batch_op.add_column(sa.Column("ai_suggested_update_level", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("ai_suggestion_reason", sa.Text(), nullable=True))
        batch_op.create_check_constraint(
            "ck_content_versions_update_level",
            "update_level in ('minor', 'medium', 'major')",
        )
        batch_op.create_check_constraint(
            "ck_content_versions_quiz_action",
            "quiz_action in ('none', 'review_related', 'generate_pack')",
        )

    with op.batch_alter_table("quiz_questions") as batch_op:
        batch_op.add_column(sa.Column("related_version_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("source_type", sa.String(length=32), nullable=False, server_default="manual"),
        )
        batch_op.add_column(
            sa.Column("review_status", sa.String(length=32), nullable=False, server_default="approved"),
        )
        batch_op.add_column(
            sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        batch_op.add_column(sa.Column("review_reason", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_quiz_questions_related_version_id",
            "content_versions",
            ["related_version_id"],
            ["id"],
        )
        batch_op.create_check_constraint(
            "ck_quiz_questions_source_type",
            "source_type in ('manual', 'ai_generated', 'ai_assisted')",
        )
        batch_op.create_check_constraint(
            "ck_quiz_questions_review_status",
            "review_status in ('draft', 'pending_review', 'approved', 'rejected')",
        )


def downgrade() -> None:
    with op.batch_alter_table("quiz_questions") as batch_op:
        batch_op.drop_constraint("ck_quiz_questions_review_status", type_="check")
        batch_op.drop_constraint("ck_quiz_questions_source_type", type_="check")
        batch_op.drop_constraint("fk_quiz_questions_related_version_id", type_="foreignkey")
        batch_op.drop_column("review_reason")
        batch_op.drop_column("needs_review")
        batch_op.drop_column("review_status")
        batch_op.drop_column("source_type")
        batch_op.drop_column("related_version_id")

    with op.batch_alter_table("content_versions") as batch_op:
        batch_op.drop_constraint("ck_content_versions_quiz_action", type_="check")
        batch_op.drop_constraint("ck_content_versions_update_level", type_="check")
        batch_op.drop_column("ai_suggestion_reason")
        batch_op.drop_column("ai_suggested_update_level")
        batch_op.drop_column("quiz_action")
        batch_op.drop_column("change_summary")
        batch_op.drop_column("update_level")
