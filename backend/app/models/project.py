from datetime import date

from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class Project(TimestampMixin, Base):
    __tablename__ = "project"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_type: Mapped[str | None] = mapped_column(String(100))
    owner_unit: Mapped[str | None] = mapped_column(String(255))
    supervision_unit: Mapped[str | None] = mapped_column(String(255))
    construction_unit: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date)
    planned_finish_date: Mapped[date | None] = mapped_column(Date)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("project_template.id"))
    default_calculation_profile_id: Mapped[int | None] = mapped_column(Integer)
    default_calculation_method: Mapped[str | None] = mapped_column(String(100), default="auto", server_default="auto")
    default_baseline_plan_id: Mapped[int | None] = mapped_column(Integer)
    dashboard_config: Mapped[str | None] = mapped_column(Text)
    report_config: Mapped[str | None] = mapped_column(Text)
    ai_config: Mapped[str | None] = mapped_column(Text)
    remark: Mapped[str | None] = mapped_column(Text)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    archive_remark: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(100))
    updated_by: Mapped[str | None] = mapped_column(String(100))
