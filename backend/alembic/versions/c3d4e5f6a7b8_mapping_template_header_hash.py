"""add header_hash to mapping_template for one-click template reuse

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-22

向 mapping_template 表新增 header_hash 字段（列名序列的 sha256 指纹），
用于"列结构完全一致"的精确匹配——配合已有的 sheet_name 字段即可在解析阶段
直接给出"一键复用"的历史模板，无需用户再次拖拽字段映射。

实际生效位置：app/services/template_matcher.py 的
compute_header_hash() / match_templates()。
"""

from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("mapping_template") as batch_op:
        batch_op.add_column(sa.Column("header_hash", sa.String(length=64), nullable=True))
        batch_op.create_index("ix_mapping_template_header_hash", ["header_hash"])


def downgrade() -> None:
    with op.batch_alter_table("mapping_template") as batch_op:
        batch_op.drop_index("ix_mapping_template_header_hash")
        batch_op.drop_column("header_hash")
