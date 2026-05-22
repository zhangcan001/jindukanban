from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BaselineSnapshotCreate(BaseModel):
    label: str = Field(..., max_length=255)
    description: str | None = None
    snapshot_date: date | None = None
    created_by: str | None = Field(default=None, max_length=100)


class BaselineSnapshotRead(BaseModel):
    id: int
    project_id: int
    baseline_plan_id: int
    snapshot_date: date | None = None
    label: str
    description: str | None = None
    item_count: int = 0
    created_by: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BaselineSnapshotDiff(BaseModel):
    snapshot_id: int
    snapshot_label: str
    snapshot_date: str | None = None
    baseline_plan_id: int
    current_item_count: int
    snapshot_item_count: int
    added_count: int
    removed_count: int
    changed_count: int
    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
