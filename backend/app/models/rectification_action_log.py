from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import CreatedAtMixin


class RectificationActionLog(CreatedAtMixin, Base):
    __tablename__ = "rectification_action_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rectification_item_id: Mapped[int] = mapped_column(ForeignKey("rectification_item.id"), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(50))
    to_status: Mapped[str | None] = mapped_column(String(50))
    content: Mapped[str | None] = mapped_column(Text)
