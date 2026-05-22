from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProgressItemEditHistory(Base):
    __tablename__ = "progress_item_edit_history"
    # 同一次"PUT /progress-items/{id}"操作产生的多行历史(用户改的字段 + 系统重算的字段)
    # 共享一个 edit_session_id（UUID）——这是撤销分组的事实依据,比"按 reason 字符串 + 2 秒
    # edited_at 窗口"那套近似算法可靠得多(后者在系统重负载或 NTP 跳变时会把同一次操作
    # 切成两组)。撤销端点直接按 edit_session_id 取回整组并回滚。
    __table_args__ = (
        Index("ix_progress_item_edit_history_session", "progress_item_id", "edit_session_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    progress_item_id: Mapped[int] = mapped_column(ForeignKey("progress_item.id"), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    edited_by: Mapped[str | None] = mapped_column(String(100))
    edit_session_id: Mapped[str | None] = mapped_column(String(36))
    edited_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

