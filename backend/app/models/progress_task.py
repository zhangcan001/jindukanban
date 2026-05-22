from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class ProgressTask(TimestampMixin, Base):
    __tablename__ = "progress_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), nullable=False)
    wbs_code: Mapped[str | None] = mapped_column(String(100))
    task_code: Mapped[str | None] = mapped_column(String(100))
    task_name: Mapped[str | None] = mapped_column(String(500))
    normalized_task_name: Mapped[str | None] = mapped_column(String(500))
    parent_task_id: Mapped[int | None] = mapped_column(ForeignKey("progress_task.id"))
    parent_task_name: Mapped[str | None] = mapped_column(String(500))
    task_level: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    area: Mapped[str | None] = mapped_column(String(255))
    building: Mapped[str | None] = mapped_column(String(255))
    floor: Mapped[str | None] = mapped_column(String(255))
    discipline: Mapped[str | None] = mapped_column(String(255))
    system_name: Mapped[str | None] = mapped_column(String(255))
    identity_key: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
