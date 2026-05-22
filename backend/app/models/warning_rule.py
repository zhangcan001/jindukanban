from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class WarningRule(TimestampMixin, Base):
    __tablename__ = "warning_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("project.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[str] = mapped_column(String(50), default="warning", server_default="warning")
    threshold_value: Mapped[float | None] = mapped_column(Float)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
