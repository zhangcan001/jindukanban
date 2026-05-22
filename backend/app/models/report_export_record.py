from datetime import datetime

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReportExportRecord(Base):
    __tablename__ = "report_export_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), nullable=False)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batch.id"))
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_path: Mapped[str | None] = mapped_column(String(500))
    data_date: Mapped[date | None] = mapped_column(Date)
    exported_by: Mapped[str | None] = mapped_column(String(100))
    exported_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
