"""add partial unique index on progress_item (batch_id, identity_key)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-22

同一批次里同一个 identity_key 只能出现一次——避免一份 Excel 在解析阶段被
读到两遍后产生两条相同的 ProgressItem，进而扭曲所有按 task 维度做的统计。
identity_key 为空字符串/NULL 的兜底行不参与该约束（它们的"身份"本就不可靠）。
"""

from alembic import op
import sqlalchemy as sa


revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # 在加约束前先清理已经存在的同 batch_id + identity_key 的重复行——保留每组最早的一行
    bind.execute(
        sa.text(
            """
            DELETE FROM progress_item
            WHERE id IN (
                SELECT pi.id FROM progress_item pi
                JOIN (
                    SELECT batch_id, identity_key, MIN(id) AS keep_id
                    FROM progress_item
                    WHERE identity_key IS NOT NULL AND identity_key != ''
                    GROUP BY batch_id, identity_key
                    HAVING COUNT(*) > 1
                ) dup
                  ON pi.batch_id = dup.batch_id
                 AND pi.identity_key = dup.identity_key
                 AND pi.id != dup.keep_id
            )
            """
        )
    )
    op.create_index(
        "uq_progress_item_batch_identity",
        "progress_item",
        ["batch_id", "identity_key"],
        unique=True,
        sqlite_where=sa.text("identity_key IS NOT NULL AND identity_key != ''"),
    )


def downgrade() -> None:
    op.drop_index("uq_progress_item_batch_identity", table_name="progress_item")
