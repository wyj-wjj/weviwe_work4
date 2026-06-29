"""add department scope permissions

Revision ID: 0007_department_scope
Revises: 0006_quiz_ai_generation_sets
Create Date: 2026-06-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0007_department_scope"
down_revision: str | None = "0006_quiz_ai_generation_sets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_departments_code", "departments", ["code"], unique=True)

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("department_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_users_department_id",
            "departments",
            ["department_id"],
            ["id"],
        )
        batch_op.create_index("ix_users_department_id", ["department_id"])

    with op.batch_alter_table("contents") as batch_op:
        batch_op.add_column(
            sa.Column("scope_type", sa.String(length=32), nullable=False, server_default="global"),
        )
        batch_op.add_column(sa.Column("department_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_contents_department_id",
            "departments",
            ["department_id"],
            ["id"],
        )
        batch_op.create_index("ix_contents_department_id", ["department_id"])
        batch_op.create_check_constraint(
            "ck_contents_scope_type",
            "scope_type in ('global', 'department')",
        )
        batch_op.create_check_constraint(
            "ck_contents_scope_department",
            "(scope_type = 'global' and department_id is null) or "
            "(scope_type = 'department' and department_id is not null)",
        )

    with op.batch_alter_table("content_versions") as batch_op:
        batch_op.add_column(
            sa.Column("scope_type", sa.String(length=32), nullable=False, server_default="global"),
        )
        batch_op.add_column(sa.Column("department_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_content_versions_department_id",
            "departments",
            ["department_id"],
            ["id"],
        )
        batch_op.create_index("ix_content_versions_department_id", ["department_id"])
        batch_op.create_check_constraint(
            "ck_content_versions_scope_type",
            "scope_type in ('global', 'department')",
        )
        batch_op.create_check_constraint(
            "ck_content_versions_scope_department",
            "(scope_type = 'global' and department_id is null) or "
            "(scope_type = 'department' and department_id is not null)",
        )

    with op.batch_alter_table("content_chunks") as batch_op:
        batch_op.add_column(
            sa.Column("scope_type", sa.String(length=32), nullable=False, server_default="global"),
        )
        batch_op.add_column(sa.Column("department_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_content_chunks_department_id",
            "departments",
            ["department_id"],
            ["id"],
        )
        batch_op.create_index("ix_content_chunks_department_id", ["department_id"])
        batch_op.create_check_constraint(
            "ck_content_chunks_scope_type",
            "scope_type in ('global', 'department')",
        )
        batch_op.create_check_constraint(
            "ck_content_chunks_scope_department",
            "(scope_type = 'global' and department_id is null) or "
            "(scope_type = 'department' and department_id is not null)",
        )


def downgrade() -> None:
    with op.batch_alter_table("content_chunks") as batch_op:
        batch_op.drop_constraint("ck_content_chunks_scope_department", type_="check")
        batch_op.drop_constraint("ck_content_chunks_scope_type", type_="check")
        batch_op.drop_index("ix_content_chunks_department_id")
        batch_op.drop_constraint("fk_content_chunks_department_id", type_="foreignkey")
        batch_op.drop_column("department_id")
        batch_op.drop_column("scope_type")

    with op.batch_alter_table("content_versions") as batch_op:
        batch_op.drop_constraint("ck_content_versions_scope_department", type_="check")
        batch_op.drop_constraint("ck_content_versions_scope_type", type_="check")
        batch_op.drop_index("ix_content_versions_department_id")
        batch_op.drop_constraint("fk_content_versions_department_id", type_="foreignkey")
        batch_op.drop_column("department_id")
        batch_op.drop_column("scope_type")

    with op.batch_alter_table("contents") as batch_op:
        batch_op.drop_constraint("ck_contents_scope_department", type_="check")
        batch_op.drop_constraint("ck_contents_scope_type", type_="check")
        batch_op.drop_index("ix_contents_department_id")
        batch_op.drop_constraint("fk_contents_department_id", type_="foreignkey")
        batch_op.drop_column("department_id")
        batch_op.drop_column("scope_type")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_department_id")
        batch_op.drop_constraint("fk_users_department_id", type_="foreignkey")
        batch_op.drop_column("department_id")

    op.drop_index("ix_departments_code", table_name="departments")
    op.drop_table("departments")
