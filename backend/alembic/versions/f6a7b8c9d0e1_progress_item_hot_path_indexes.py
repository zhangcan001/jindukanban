"""add hot-path indexes on progress_item

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-22

所有 dashboard / analytics / warnings 查询都走 (project_id, batch_id) 入口,
_find_previous_item 按 task_id 跨批次找上一期数据,status 是常用筛选维度。
之前只有 FK 上的隐式索引,在单项目数据量 5000+ 行 / 多批次场景下出现明显
扫描成本(SQLite 每次都得做 partial scan)。本迁移给这三条热路径加显式
非唯一索引,不影响写入语义,仅查询加速。
"""

from alembic import op


revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_progress_item_project_batch",
        "progress_item",
        ["project_id", "batch_id"],
    )
    op.create_index(
        "ix_progress_item_task_id",
        "progress_item",
        ["task_id"],
    )
    op.create_index(
        "ix_progress_item_batch_status",
        "progress_item",
        ["batch_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_progress_item_batch_status", table_name="progress_item")
    op.drop_index("ix_progress_item_task_id", table_name="progress_item")
    op.drop_index("ix_progress_item_project_batch", table_name="progress_item")
