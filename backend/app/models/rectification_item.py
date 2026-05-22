from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class RectificationItem(TimestampMixin, Base):
    __tablename__ = "rectification_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), nullable=False)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batch.id"))
    progress_item_id: Mapped[int | None] = mapped_column(ForeignKey("progress_item.id"))
    warning_record_id: Mapped[int | None] = mapped_column(ForeignKey("warning_record.id"))
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[int | None] = mapped_column(Integer)
    discipline: Mapped[str | None] = mapped_column(String(255))
    building: Mapped[str | None] = mapped_column(String(255))
    floor: Mapped[str | None] = mapped_column(String(255))
    system_name: Mapped[str | None] = mapped_column(String(255))
    task_name: Mapped[str | None] = mapped_column(String(500))
    issue_description: Mapped[str | None] = mapped_column(Text)
    delay_level: Mapped[str | None] = mapped_column(String(50))
    actual_percent: Mapped[float | None] = mapped_column(Float)
    planned_percent: Mapped[float | None] = mapped_column(Float)
    progress_deviation: Mapped[float | None] = mapped_column(Float)
    responsible_person: Mapped[str | None] = mapped_column(String(100))
    responsible_unit: Mapped[str | None] = mapped_column(String(255))
    planned_finish_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(50), default="open", server_default="open")
    review_result: Mapped[str | None] = mapped_column(Text)
    remark: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
