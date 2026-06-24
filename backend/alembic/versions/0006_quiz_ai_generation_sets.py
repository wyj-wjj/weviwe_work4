"""add quiz ai generation batches and quiz sets

Revision ID: 0006_quiz_ai_generation_sets
Revises: 0005_quiz_update_policy
Create Date: 2026-06-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0006_quiz_ai_generation_sets"
down_revision: str | None = "0005_quiz_update_policy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quiz_generation_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("update_level", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("requested_count", sa.Integer(), nullable=False),
        sa.Column("generated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "update_level in ('minor', 'medium', 'major')",
            name="ck_quiz_generation_batches_update_level",
        ),
        sa.CheckConstraint(
            "status in ('pending', 'completed', 'failed')",
            name="ck_quiz_generation_batches_status",
        ),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["version_id"], ["content_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quiz_generation_batches_content_id", "quiz_generation_batches", ["content_id"])
    op.create_index("ix_quiz_generation_batches_version_id", "quiz_generation_batches", ["version_id"])

    with op.batch_alter_table("quiz_questions") as batch_op:
        batch_op.add_column(sa.Column("generation_batch_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("priority", sa.Integer(), nullable=False, server_default="0"))
        batch_op.create_foreign_key(
            "fk_quiz_questions_generation_batch_id",
            "quiz_generation_batches",
            ["generation_batch_id"],
            ["id"],
        )
        batch_op.create_index("ix_quiz_questions_generation_batch_id", ["generation_batch_id"])

    op.create_table(
        "quiz_sets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("related_content_id", sa.Integer(), nullable=False),
        sa.Column("related_version_id", sa.Integer(), nullable=False),
        sa.Column("update_level", sa.String(length=32), nullable=False),
        sa.Column("permission_level", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "update_level in ('minor', 'medium', 'major')",
            name="ck_quiz_sets_update_level",
        ),
        sa.CheckConstraint(
            "permission_level in ('general', 'full')",
            name="ck_quiz_sets_permission_level",
        ),
        sa.CheckConstraint(
            "status in ('active', 'inactive')",
            name="ck_quiz_sets_status",
        ),
        sa.ForeignKeyConstraint(["related_content_id"], ["contents.id"]),
        sa.ForeignKeyConstraint(["related_version_id"], ["content_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quiz_sets_related_content_id", "quiz_sets", ["related_content_id"])
    op.create_index("ix_quiz_sets_related_version_id", "quiz_sets", ["related_version_id"])

    op.create_table(
        "quiz_question_set_items",
        sa.Column("quiz_set_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["question_id"], ["quiz_questions.id"]),
        sa.ForeignKeyConstraint(["quiz_set_id"], ["quiz_sets.id"]),
        sa.PrimaryKeyConstraint("quiz_set_id", "question_id"),
    )


def downgrade() -> None:
    op.drop_table("quiz_question_set_items")
    op.drop_index("ix_quiz_sets_related_version_id", table_name="quiz_sets")
    op.drop_index("ix_quiz_sets_related_content_id", table_name="quiz_sets")
    op.drop_table("quiz_sets")

    with op.batch_alter_table("quiz_questions") as batch_op:
        batch_op.drop_index("ix_quiz_questions_generation_batch_id")
        batch_op.drop_constraint("fk_quiz_questions_generation_batch_id", type_="foreignkey")
        batch_op.drop_column("priority")
        batch_op.drop_column("expires_at")
        batch_op.drop_column("generation_batch_id")

    op.drop_index("ix_quiz_generation_batches_version_id", table_name="quiz_generation_batches")
    op.drop_index("ix_quiz_generation_batches_content_id", table_name="quiz_generation_batches")
    op.drop_table("quiz_generation_batches")
