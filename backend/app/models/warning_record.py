from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import CreatedAtMixin


class WarningRecord(CreatedAtMixin, Base):
    __tablename__ = "warning_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), nullable=False)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batch.id"))
    task_id: Mapped[int | None] = mapped_column(ForeignKey("progress_task.id"))
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("warning_rule.id"))
    level: Mapped[str | None] = mapped_column(String(50))
    title: Mapped[str | None] = mapped_column(String(255))
    message: Mapped[str | None] = mapped_column(Text)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    resolution_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
