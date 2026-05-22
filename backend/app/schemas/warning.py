from datetime import datetime

from pydantic import BaseModel


class WarningRuleBase(BaseModel):
    name: str
    rule_type: str
    level: str = "warning"
    threshold_value: float | None = None
    is_enabled: bool = True


class WarningRuleCreate(WarningRuleBase):
    pass


class WarningRuleUpdate(BaseModel):
    name: str | None = None
    level: str | None = None
    threshold_value: float | None = None
    is_enabled: bool | None = None


class WarningRuleRead(WarningRuleBase):
    id: int
    project_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WarningRecordRead(BaseModel):
    id: int
    project_id: int
    batch_id: int | None = None
    progress_item_id: int | None = None
    task_id: int | None = None
    rule_id: int | None = None
    rule_name: str | None = None
    level: str | None = None
    level_label: str
    status: str
    status_label: str
    title: str | None = None
    message: str | None = None
    warning_message: str
    task_name: str
    discipline: str
    building: str
    floor: str
    system_name: str
    unit: str | None = None
    actual_percent: float | None = None
    planned_percent: float | None = None
    progress_deviation: float | None = None
    is_resolved: bool
    created_at: datetime
    handled_at: datetime | None = None
    remark: str | None = None
    rectification_item_id: int | None = None
    has_rectification: bool = False

    model_config = {"from_attributes": True}


class WarningRunResponse(BaseModel):
    batch_id: int
    generated_count: int
    records: list[WarningRecordRead]


class WarningFilterOptions(BaseModel):
    disciplines: list[str] = []
    buildings: list[str] = []
    floors: list[str] = []
    floors_by_building: dict[str, list[str]] = {}
