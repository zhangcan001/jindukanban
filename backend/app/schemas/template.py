from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.mapping import FieldMapping


class ProjectTemplateRead(BaseModel):
    id: int
    name: str
    code: str
    description: str | None = None
    project_type: str | None = None
    is_builtin: bool
    is_active: bool
    default_calculation_profile: str | None = None
    default_warning_rules: str | None = None
    default_field_aliases: str | None = None
    default_dashboard_config: str | None = None
    default_report_config: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    project_type: str | None = None
    is_active: bool | None = None


class MappingTemplateDetail(BaseModel):
    id: int
    project_id: int | None = None
    name: str
    description: str | None = None
    project_type: str | None = None
    is_global: bool
    is_active: bool
    last_used_at: datetime | None = None
    use_count: int = 0
    fields: list[FieldMapping] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MappingTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    project_type: str | None = None
    is_active: bool | None = None
