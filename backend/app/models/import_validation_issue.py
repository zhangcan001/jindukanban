from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import CreatedAtMixin


class ImportValidationIssue(CreatedAtMixin, Base):
    __tablename__ = "import_validation_issue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batch.id"), nullable=False)
    row_index: Mapped[int | None] = mapped_column(Integer)
    column_name: Mapped[str | None] = mapped_column(String(255))
    level: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str | None] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text, nullable=False)
