from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class ProgressItemRead(BaseModel):
    id: int
    project_id: int
    batch_id: int
    task_id: int | None = None
    baseline_plan_id: int | None = None
    wbs_code: str | None = None
    task_code: str | None = None
    task_name: str | None = None
    area: str | None = None
    construction_unit: str | None = None
    building: str | None = None
    floor: str | None = None
    discipline: str | None = None
    system_name: str | None = None
    unit: str | None = None
    total_quantity: float | None = None
    planned_quantity: float | None = None
    period_quantity: float | None = None
    cumulative_quantity: float | None = None
    actual_quantity: float | None = None
    remaining_quantity: float | None = None
    planned_percent: float | None = None
    imported_planned_percent: float | None = None
    actual_percent: float | None = None
    reported_percent: float | None = None
    time_planned_percent: float | None = None
    progress_deviation: float | None = None
    schedule_phase: str | None = None
    current_period_quantity: float | None = None
    current_period_percent: float | None = None
    planned_start_date: date | None = None
    planned_finish_date: date | None = None
    actual_start_date: date | None = None
    actual_finish_date: date | None = None
    weight: float | None = None
    value_amount: float | None = None
    status: str | None = None
    remark: str | None = None
    extra_fields: str | None = None
    is_manually_edited: bool
    manual_edit_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProgressItemScopeInfo(BaseModel):
    scope: str
    data_date: date | None = None
    import_group_id: str | None = None
    included_batch_ids: list[int] = []
    included_sheets: list[str] = []
    task_count: int = 0
    message: str | None = None


class ProgressItemListResponse(BaseModel):
    items: list[ProgressItemRead]
    total: int
    page: int
    page_size: int
    scope_info: ProgressItemScopeInfo | None = None


class ProgressItemUpdate(BaseModel):
    reason: str = Field(..., min_length=1)
    actual_quantity: float | None = None
    cumulative_quantity: float | None = None
    period_quantity: float | None = None
    planned_quantity: float | None = None
    total_quantity: float | None = None
    actual_percent: float | None = None
    planned_percent: float | None = None
    reported_percent: float | None = None
    remaining_quantity: float | None = None
    planned_start_date: date | None = None
    planned_finish_date: date | None = None
    actual_start_date: date | None = None
    actual_finish_date: date | None = None
    weight: float | None = None
    value_amount: float | None = None
    status: str | None = None
    remark: str | None = None


class ProgressItemFilterOptions(BaseModel):
    construction_units: list[str] = []
    buildings: list[str] = []
    floors: list[str] = []
    disciplines: list[str] = []
    system_names: list[str] = []
    statuses: list[str] = []
    floors_by_building: dict[str, list[str]] = {}


class ProgressItemEditHistoryRead(BaseModel):
    id: int
    progress_item_id: int
    field_name: str
    old_value: str | None = None
    new_value: str | None = None
    reason: str | None = None
    edited_by: str | None = None
    edited_at: datetime

    model_config = {"from_attributes": True}
