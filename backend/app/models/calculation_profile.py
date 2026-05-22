from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class CalculationProfile(TimestampMixin, Base):
    __tablename__ = "calculation_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("project.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    overall_algorithm: Mapped[str] = mapped_column(String(100), default="avg_percent", server_default="avg_percent")
    group_algorithm: Mapped[str] = mapped_column(String(100), default="avg_percent", server_default="avg_percent")
    percent_source: Mapped[str] = mapped_column(String(100), default="provided_percent_first", server_default="provided_percent_first")
    use_weight: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    weight_field: Mapped[str | None] = mapped_column(String(100))
    use_value_amount: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    value_field: Mapped[str | None] = mapped_column(String(100))
    allow_mixed_unit_sum: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    enable_date_plan_calculation: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # 偏差阈值（progress_deviation = actual - planned，单位为百分点）：
    #   >= ahead          → ahead（超前）
    #   >= normal         → normal（正常）
    #   >= minor          → slightly_delayed（轻微滞后）
    #   >= major          → delayed（滞后）
    #   <  major          → seriously_delayed（严重滞后）
    delay_threshold_ahead: Mapped[float] = mapped_column(Float, default=5.0, server_default="5")
    delay_threshold_normal: Mapped[float] = mapped_column(Float, default=-5.0, server_default="-5")
    delay_threshold_minor: Mapped[float] = mapped_column(Float, default=-10.0, server_default="-10")
    delay_threshold_major: Mapped[float] = mapped_column(Float, default=-20.0, server_default="-20")
    # 按专业 / 楼层等维度的覆盖配置（JSON 字符串），格式：
    # {"discipline": {"机电": {"normal": -3, "minor": -8, "major": -15}}, ...}
    delay_threshold_overrides: Mapped[str | None] = mapped_column(Text)
