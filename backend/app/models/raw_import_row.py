from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import CreatedAtMixin


class RawImportRow(CreatedAtMixin, Base):
    __tablename__ = "raw_import_row"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batch.id"), nullable=False)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[str] = mapped_column(Text, nullable=False)
