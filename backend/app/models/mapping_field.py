from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class MappingField(TimestampMixin, Base):
    __tablename__ = "mapping_field"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("mapping_template.id"), nullable=False)
    excel_column_name: Mapped[str] = mapped_column(String(255), nullable=False)
    system_field_name: Mapped[str | None] = mapped_column(String(100))
    field_type: Mapped[str | None] = mapped_column(String(50))
    is_dimension: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    is_metric: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    save_to_extra: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
