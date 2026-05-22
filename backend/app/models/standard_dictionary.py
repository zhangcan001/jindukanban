from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class StandardDictionary(TimestampMixin, Base):
    __tablename__ = "standard_dictionary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("project.id"))
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_value: Mapped[str] = mapped_column(String(255), nullable=False)
    standard_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_global: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
