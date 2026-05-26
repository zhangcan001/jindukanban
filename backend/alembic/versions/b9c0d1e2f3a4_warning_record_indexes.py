"""add hot-path indexes on warning_record

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-05-26

预警中心分页查询 (新加的 /warnings/page) 经常用
WHERE project_id = ? AND batch_id = ? AND [level/is_resolved/resolution_type 任意组合]
ORDER BY created_at DESC LIMIT N OFFSET M。
warning_record 当前没有显式索引,FK 在 SQLite 里也不会自动建索引,
随着记录数量上升 (现在 320,生产场景多批次 × 多项目会到 5000+) 单页查询会逐渐变慢。

本迁移加 3 个非唯一复合索引,只影响读路径性能,不改变写入语义:
- (project_id, batch_id, created_at) — 列表分页主路径
- (project_id, is_resolved)          — "只看未处理" 开关 / 状态过滤
- (rule_id)                          — 与 warning_rule 关联查询
"""

from alembic import op


revision = "b9c0d1e2f3a4"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_warning_record_project_batch_created",
        "warning_record",
        ["project_id", "batch_id", "created_at"],
    )
    op.create_index(
        "ix_warning_record_project_resolved",
        "warning_record",
        ["project_id", "is_resolved"],
    )
    op.create_index(
        "ix_warning_record_rule_id",
        "warning_record",
        ["rule_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_warning_record_rule_id", table_name="warning_record")
    op.drop_index("ix_warning_record_project_resolved", table_name="warning_record")
    op.drop_index("ix_warning_record_project_batch_created", table_name="warning_record")
