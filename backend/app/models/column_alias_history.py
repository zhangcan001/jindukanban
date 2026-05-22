from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class ColumnAliasHistory(TimestampMixin, Base):
    __tablename__ = "column_alias_history"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "normalized_header",
            "system_field",
            name="uq_column_alias_scope_header_field",
        ),
        Index("ix_column_alias_normalized_header", "normalized_header"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("project.id"))
    raw_header: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_header: Mapped[str] = mapped_column(String(512), nullable=False)
    system_field: Mapped[str] = mapped_column(String(100), nullable=False)
    field_type: Mapped[str | None] = mapped_column(String(50))
    hit_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
