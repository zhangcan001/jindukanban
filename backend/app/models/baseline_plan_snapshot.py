from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import CreatedAtMixin


class BaselinePlanSnapshot(CreatedAtMixin, Base):
    __tablename__ = "baseline_plan_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), nullable=False)
    baseline_plan_id: Mapped[int] = mapped_column(ForeignKey("baseline_plan.id"), nullable=False)
    snapshot_date: Mapped[date | None] = mapped_column(Date)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_by: Mapped[str | None] = mapped_column(String(100))
