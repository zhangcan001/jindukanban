from datetime import date, datetime

from pydantic import BaseModel, Field


class RectificationBase(BaseModel):
    batch_id: int | None = None
    discipline: str | None = None
    building: str | None = None
    floor: str | None = None
    system_name: str | None = None
    task_name: str | None = None
    issue_description: str | None = None
    delay_level: str | None = None
    responsible_person: str | None = None
    responsible_unit: str | None = None
    planned_finish_date: date | None = None
    status: str = "open"
    review_result: str | None = None
    remark: str | None = None


class RectificationCreate(RectificationBase):
    source_type: str = "manual"


class RectificationUpdate(BaseModel):
    responsible_person: str | None = None
    responsible_unit: str | None = None
    planned_finish_date: date | None = None
    status: str | None = None
    review_result: str | None = None
    remark: str | None = None


class RectificationStatusUpdate(BaseModel):
    status: str
    remark: str | None = None


class RectificationFromDelayedItem(BaseModel):
    batch_id: int
    progress_item_id: int


class RectificationFromWarningRecord(BaseModel):
    warning_record_id: int


class RectificationRead(BaseModel):
    id: int
    project_id: int
    batch_id: int | None = None
    source_batch_label: str | None = None
    source_baseline_plan_id: int | None = None
    source_baseline_plan_name: str | None = None
    progress_item_id: int | None = None
    warning_record_id: int | None = None
    source_type: str
    source_id: int | None = None
    source_label: str
    discipline: str | None = None
    building: str | None = None
    floor: str | None = None
    system_name: str | None = None
    task_name: str | None = None
    issue_description: str | None = None
    delay_level: str | None = None
    delay_level_label: str
    actual_percent: float | None = None
    planned_percent: float | None = None
    progress_deviation: float | None = None
    responsible_person: str | None = None
    responsible_unit: str | None = None
    planned_finish_date: date | None = None
    status: str
    status_label: str
    review_result: str | None = None
    remark: str | None = None
    is_overdue: bool
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None

    model_config = {"from_attributes": True}


class RectificationListResponse(BaseModel):
    items: list[RectificationRead]
    total: int
    page: int = 1
    page_size: int = 20


class RectificationSummary(BaseModel):
    total: int = 0
    open: int = 0
    in_progress: int = 0
    completed: int = 0
    closed: int = 0
    ignored: int = 0
    overdue: int = 0
    serious: int = 0
    new_this_week: int = 0
    closed_this_week: int = 0


class RectificationCreateResponse(BaseModel):
    item: RectificationRead
    created: bool
    message: str


class RectificationExportFilters(BaseModel):
    status: str | None = Field(default=None)
    discipline: str | None = None
    building: str | None = None
    floor: str | None = None
    delay_level: str | None = None
    keyword: str | None = None


class RectificationBatchUpdate(BaseModel):
    ids: list[int]
    status: str | None = None
    responsible_person: str | None = None
    responsible_unit: str | None = None
    planned_finish_date: date | None = None
    remark: str | None = None


class RectificationBatchUpdateResponse(BaseModel):
    updated_count: int
    skipped_count: int
    skipped_ids: list[int] = []


class RectificationFilterOptions(BaseModel):
    disciplines: list[str] = []
    buildings: list[str] = []
    floors: list[str] = []
    responsible_persons: list[str] = []
    responsible_units: list[str] = []
    delay_levels: list[str] = []
    statuses: list[str] = []
    source_types: list[str] = []
    floors_by_building: dict[str, list[str]] = {}


class RectificationActionLogRead(BaseModel):
    id: int
    rectification_item_id: int
    project_id: int
    action: str
    action_label: str
    operator: str = "本地用户"
    from_status: str | None = None
    from_status_label: str | None = None
    to_status: str | None = None
    to_status_label: str | None = None
    content: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
