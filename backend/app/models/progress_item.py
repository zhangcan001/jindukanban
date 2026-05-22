from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class ProgressItem(TimestampMixin, Base):
    __tablename__ = "progress_item"
    # 同一批次内 identity_key 不允许重复——避免一份 Excel 里某行被读到两遍写出两条
    # ProgressItem，从而扭曲后续按 task 维度做的统计。identity_key 为空(""/NULL)的
    # 兜底行不参与约束，因为它们的"身份"本来就不可靠。
    __table_args__ = (
        Index(
            "uq_progress_item_batch_identity",
            "batch_id",
            "identity_key",
            unique=True,
            sqlite_where=text("identity_key IS NOT NULL AND identity_key != ''"),
        ),
        # 高频访问路径加索引——所有 dashboard/analytics 查询都走 (project_id, batch_id)
        # 入口,_find_previous_item 跨批次按 task_id 找上一批数据,status 是常用筛选项。
        # 不给 building/floor/discipline 单独建索引——它们总是和 batch_id 一起出现在
        # WHERE 里,(project_id, batch_id) 已经把候选集缩到几百到几千行,再过滤已经够快。
        Index("ix_progress_item_project_batch", "project_id", "batch_id"),
        Index("ix_progress_item_task_id", "task_id"),
        Index("ix_progress_item_batch_status", "batch_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), nullable=False)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batch.id"), nullable=False)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("progress_task.id"))
    baseline_plan_id: Mapped[int | None] = mapped_column(ForeignKey("baseline_plan.id"))
    identity_key: Mapped[str | None] = mapped_column(String(500))
    wbs_code: Mapped[str | None] = mapped_column(String(100))
    task_code: Mapped[str | None] = mapped_column(String(100))
    task_name: Mapped[str | None] = mapped_column(String(500))
    parent_task_name: Mapped[str | None] = mapped_column(String(500))
    area: Mapped[str | None] = mapped_column(String(255))
    construction_unit: Mapped[str | None] = mapped_column(String(255))
    building: Mapped[str | None] = mapped_column(String(255))
    floor: Mapped[str | None] = mapped_column(String(255))
    discipline: Mapped[str | None] = mapped_column(String(255))
    system_name: Mapped[str | None] = mapped_column(String(255))
    unit: Mapped[str | None] = mapped_column(String(50))
    total_quantity: Mapped[float | None] = mapped_column(Float)
    planned_quantity: Mapped[float | None] = mapped_column(Float)
    period_quantity: Mapped[float | None] = mapped_column(Float)
    cumulative_quantity: Mapped[float | None] = mapped_column(Float)
    actual_quantity: Mapped[float | None] = mapped_column(Float)
    remaining_quantity: Mapped[float | None] = mapped_column(Float)
    planned_percent: Mapped[float | None] = mapped_column(Float)
    """计划完成率(最终采用的)——通常由 progress_calculator 选定:
    优先 imported_planned_percent(导入的原始计划完成率),次选按计划日期算的
    time_planned_percent。所有 dashboard / 偏差计算都用这一列。"""
    imported_planned_percent: Mapped[float | None] = mapped_column(Float)
    """Excel 直接导入的"计划完成率"原始值——保留以便溯源,不会被 progress_calculator
    覆盖。如果用户重新导入或调整数据,这一列就是"原始计划"的事实依据。"""
    actual_percent: Mapped[float | None] = mapped_column(Float)
    """实际完成率(最终采用的)——progress_calculator 计算后的结果。优先按
    工程量 (actual_quantity / total_quantity) 计算,次选导入的实际完成率。"""
    reported_percent: Mapped[float | None] = mapped_column(Float)
    """上报完成率——施工方/分包单位自报的进度。通常用于和真实计算结果对比、
    分析"汇报水分",不直接参与 dashboard 主指标计算。"""
    time_planned_percent: Mapped[float | None] = mapped_column(Float)
    """按计划日期推算的"截至 data_date 应完成率",即
    (data_date - planned_start_date) / (planned_finish_date - planned_start_date)。
    用于在 imported_planned_percent 缺失时回退,以及计算"按时间应到/实际差距"。"""
    progress_deviation: Mapped[float | None] = mapped_column(Float)
    schedule_phase: Mapped[str | None] = mapped_column(String(50))
    current_period_quantity: Mapped[float | None] = mapped_column(Float)
    current_period_percent: Mapped[float | None] = mapped_column(Float)
    planned_start_date: Mapped[date | None] = mapped_column(Date)
    planned_finish_date: Mapped[date | None] = mapped_column(Date)
    actual_start_date: Mapped[date | None] = mapped_column(Date)
    actual_finish_date: Mapped[date | None] = mapped_column(Date)
    weight: Mapped[float | None] = mapped_column(Float)
    value_amount: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str | None] = mapped_column(String(50))
    remark: Mapped[str | None] = mapped_column(Text)
    extra_fields: Mapped[str | None] = mapped_column(Text)
    is_manually_edited: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    manual_edit_reason: Mapped[str | None] = mapped_column(Text)
