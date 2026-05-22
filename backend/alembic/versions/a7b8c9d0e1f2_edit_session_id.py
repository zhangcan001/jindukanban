"""add edit_session_id to progress_item_edit_history

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-22

撤销最近一次修改的分组之前用"reason 字符串 + 2 秒 edited_at 窗口"近似,在系统重载
或 NTP 跳变下会把同一次操作切成两组,撤销不全。增加 edit_session_id(UUID)直接标记
"哪些历史行是同一次操作产生的",撤销改成单条 WHERE edit_session_id = ? 即可。
旧数据 edit_session_id 为 NULL,撤销端点对它们继续走旧的兜底分组逻辑,保留向后兼容。
"""

from alembic import op
import sqlalchemy as sa


revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "progress_item_edit_history",
        sa.Column("edit_session_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_progress_item_edit_history_session",
        "progress_item_edit_history",
        ["progress_item_id", "edit_session_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_progress_item_edit_history_session", table_name="progress_item_edit_history")
    op.drop_column("progress_item_edit_history", "edit_session_id")
