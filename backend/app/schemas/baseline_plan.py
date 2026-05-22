from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class BaselinePlanBase(BaseModel):
    name: str
    plan_type: str = "current"
    description: str | None = None
    baseline_date: date | None = None
    is_default: bool = False
    is_active: bool = True


class BaselinePlanCreate(BaselinePlanBase):
    pass


class BaselinePlanUpdate(BaseModel):
    name: str | None = None
    plan_type: str | None = None
    description: str | None = None
    baseline_date: date | None = None
    is_default: bool | None = None
    is_active: bool | None = None


class BaselinePlanRead(BaselinePlanBase):
    id: int
    project_id: int
    bound_batch_count: int = 0
    latest_bound_batch_date: date | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BaselineBoundBatch(BaseModel):
    id: int
    project_id: int
    file_name: str
    sheet_name: str | None = None
    data_date: date | None = None
    status: str
    imported_count: int = 0
    published_at: datetime | None = None
    created_at: datetime
    baseline_plan_id: int | None = None
    baseline_plan_name: str | None = None

    model_config = ConfigDict(from_attributes=True)
