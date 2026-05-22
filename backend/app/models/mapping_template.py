from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class MappingTemplate(TimestampMixin, Base):
    __tablename__ = "mapping_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("project.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    project_type: Mapped[str | None] = mapped_column(String(100))
    sheet_name: Mapped[str | None] = mapped_column(String(255))
    header_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    field_structure: Mapped[str | None] = mapped_column(Text)
    is_global: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    use_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
