"""add column_alias_history

Revision ID: a1b2c3d4e5f6
Revises: 90544b42528d
Create Date: 2026-05-22

为列名识别提供历史学习表：用户每次确认导入后，记录
(excel_column_name → system_field) 形成可复用的别名库。
配套服务：app/services/column_alias_service.py。
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "90544b42528d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "column_alias_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id"), nullable=True),
        sa.Column("raw_header", sa.String(length=512), nullable=False),
        sa.Column("normalized_header", sa.String(length=512), nullable=False),
        sa.Column("system_field", sa.String(length=100), nullable=False),
        sa.Column("field_type", sa.String(length=50), nullable=True),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "project_id", "normalized_header", "system_field",
            name="uq_column_alias_scope_header_field",
        ),
    )
    op.create_index(
        "ix_column_alias_normalized_header",
        "column_alias_history",
        ["normalized_header"],
    )


def downgrade() -> None:
    op.drop_index("ix_column_alias_normalized_header", table_name="column_alias_history")
    op.drop_table("column_alias_history")
