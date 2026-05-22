from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class ProjectTemplate(TimestampMixin, Base):
    __tablename__ = "project_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    project_type: Mapped[str | None] = mapped_column(String(100))
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    default_calculation_profile: Mapped[str | None] = mapped_column(Text)
    default_warning_rules: Mapped[str | None] = mapped_column(Text)
    default_field_aliases: Mapped[str | None] = mapped_column(Text)
    default_dashboard_config: Mapped[str | None] = mapped_column(Text)
    default_report_config: Mapped[str | None] = mapped_column(Text)
