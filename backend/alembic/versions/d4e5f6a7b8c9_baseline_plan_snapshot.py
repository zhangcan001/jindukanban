"""add baseline_plan_snapshot table for plan version snapshotting

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-22

为 baseline_plan 引入"版本快照"能力：在某个时间点冻结一份 ProgressItem 的
计划部分（计划开始/完成日期、计划完成率、imported_planned_percent、weight 等）
作为 JSON payload 写入 baseline_plan_snapshot 表，后续可与"当前进度数据"比对，
回答"和上次基线/上周快照相比，计划/实际偏差有多少"的问题。

只动表结构，不动现有计算逻辑——快照内容由
app/services/baseline_snapshot_service.py 维护。
"""

from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "baseline_plan_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("baseline_plan_id", sa.Integer(), sa.ForeignKey("baseline_plan.id"), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_baseline_plan_snapshot_baseline", "baseline_plan_snapshot", ["baseline_plan_id"])
    op.create_index("ix_baseline_plan_snapshot_project", "baseline_plan_snapshot", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_baseline_plan_snapshot_project", table_name="baseline_plan_snapshot")
    op.drop_index("ix_baseline_plan_snapshot_baseline", table_name="baseline_plan_snapshot")
    op.drop_table("baseline_plan_snapshot")
