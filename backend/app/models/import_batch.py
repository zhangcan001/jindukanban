from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class ImportBatch(TimestampMixin, Base):
    __tablename__ = "import_batch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(500))
    sheet_name: Mapped[str | None] = mapped_column(String(255))
    import_group_id: Mapped[str | None] = mapped_column(String(100))
    import_group_name: Mapped[str | None] = mapped_column(String(255))
    data_date: Mapped[date | None] = mapped_column(Date)
    header_row_index: Mapped[int | None] = mapped_column(Integer)
    data_start_row_index: Mapped[int | None] = mapped_column(Integer)
    multi_header: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    header_end_row_index: Mapped[int | None] = mapped_column(Integer)
    row_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    imported_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    warning_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    data_quality_score: Mapped[float | None] = mapped_column(Float)
    field_completeness: Mapped[float | None] = mapped_column(Float)
    task_match_rate: Mapped[float | None] = mapped_column(Float)
    valid_row_rate: Mapped[float | None] = mapped_column(Float)
    plan_field_completeness: Mapped[float | None] = mapped_column(Float)
    unit_consistency: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50), default="draft", server_default="draft")
    mapping_template_id: Mapped[int | None] = mapped_column(Integer)
    calculation_profile_id: Mapped[int | None] = mapped_column(ForeignKey("calculation_profile.id"))
    baseline_plan_id: Mapped[int | None] = mapped_column(ForeignKey("baseline_plan.id"))
    batch_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    is_frozen: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime)
    freeze_remark: Mapped[str | None] = mapped_column(Text)
    replaced_batch_id: Mapped[int | None] = mapped_column(Integer)
    import_strategy: Mapped[str | None] = mapped_column(String(50))
    error_report: Mapped[str | None] = mapped_column(Text)
    imported_by: Mapped[str | None] = mapped_column(String(100))
    confirmed_by: Mapped[str | None] = mapped_column(String(100))
    published_by: Mapped[str | None] = mapped_column(String(100))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
