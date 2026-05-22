"""add configurable delay thresholds to calculation_profile

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-22

向 calculation_profile 表新增 5 个字段，使滞后阈值可按 profile 配置：
- delay_threshold_ahead   (>= 此值 → 超前)
- delay_threshold_normal  (>= 此值 → 正常)
- delay_threshold_minor   (>= 此值 → 轻微滞后)
- delay_threshold_major   (>= 此值 → 明显滞后；小于此值 → 严重滞后)
- delay_threshold_overrides (JSON 字符串，按 discipline/floor/building 维度覆盖)

阈值实际生效位置：app/services/progress_calculator.py 的
resolve_delay_thresholds() / classify_delay_status()。
"""

from alembic import op
import sqlalchemy as sa


revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("calculation_profile") as batch_op:
        batch_op.add_column(sa.Column("delay_threshold_ahead", sa.Float(), nullable=False, server_default="5"))
        batch_op.add_column(sa.Column("delay_threshold_normal", sa.Float(), nullable=False, server_default="-5"))
        batch_op.add_column(sa.Column("delay_threshold_minor", sa.Float(), nullable=False, server_default="-10"))
        batch_op.add_column(sa.Column("delay_threshold_major", sa.Float(), nullable=False, server_default="-20"))
        batch_op.add_column(sa.Column("delay_threshold_overrides", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("calculation_profile") as batch_op:
        batch_op.drop_column("delay_threshold_overrides")
        batch_op.drop_column("delay_threshold_major")
        batch_op.drop_column("delay_threshold_minor")
        batch_op.drop_column("delay_threshold_normal")
        batch_op.drop_column("delay_threshold_ahead")
