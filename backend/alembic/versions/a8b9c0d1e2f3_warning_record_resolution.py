"""add resolution_type / handled_at / remark to warning_record

Revision ID: a8b9c0d1e2f3
Revises: f6a7b8c9d0e1
Create Date: 2026-05-26

WarningRecord 之前只有 is_resolved (bool)，前端无法区分"已处理 / 已忽略"，
也无法记录处理时间和备注。本迁移补齐三个字段，使预警闭环操作的状态可见可追溯：
- resolution_type   (handled | ignored，None 表示未处理)
- handled_at        (datetime，处理或忽略的时间戳)
- remark            (text，处理备注 / 忽略原因)
"""

from alembic import op
import sqlalchemy as sa


revision = "a8b9c0d1e2f3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("warning_record") as batch_op:
        batch_op.add_column(sa.Column("resolution_type", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("handled_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("remark", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("warning_record") as batch_op:
        batch_op.drop_column("remark")
        batch_op.drop_column("handled_at")
        batch_op.drop_column("resolution_type")
