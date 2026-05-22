from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ProjectBase(BaseModel):
    name: str
    project_type: str | None = None
    owner_unit: str | None = None
    supervision_unit: str | None = None
    construction_unit: str | None = None
    start_date: date | None = None
    planned_finish_date: date | None = None
    template_id: int | None = None
    default_calculation_profile_id: int | None = None
    default_calculation_method: str | None = "auto"
    default_baseline_plan_id: int | None = None
    dashboard_config: str | None = None
    report_config: str | None = None
    ai_config: str | None = None
    remark: str | None = None
    is_archived: bool = False
    archive_remark: str | None = None
    created_by: str | None = None
    updated_by: str | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = None
    project_type: str | None = None
    owner_unit: str | None = None
    supervision_unit: str | None = None
    construction_unit: str | None = None
    start_date: date | None = None
    planned_finish_date: date | None = None
    template_id: int | None = None
    default_calculation_profile_id: int | None = None
    default_calculation_method: str | None = None
    default_baseline_plan_id: int | None = None
    dashboard_config: str | None = None
    report_config: str | None = None
    ai_config: str | None = None
    remark: str | None = None
    is_archived: bool | None = None
    archive_remark: str | None = None
    updated_by: str | None = None


class ProjectArchiveRequest(BaseModel):
    archive_remark: str | None = None


class ProjectRead(ProjectBase):
    id: int
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
