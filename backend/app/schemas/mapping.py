from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FieldMapping(BaseModel):
    excel_column_name: str
    recommended_field: str | None = None
    system_field_name: str | None = None
    field_type: str = "unknown"
    is_dimension: bool = False
    is_metric: bool = False
    is_required: bool = False
    save_to_extra: bool = True
    sort_order: int = 0
    match_type: str | None = None
    confidence: str | None = None
    reason: str | None = None
    field_role: str | None = None
    affects_statistics: bool = False
    affects_delay: bool = False


class MappingFieldRead(BaseModel):
    id: int
    template_id: int
    excel_column_name: str
    system_field_name: str | None = None
    field_type: str | None = None
    is_dimension: bool = False
    is_metric: bool = False
    is_required: bool = False
    save_to_extra: bool = True
    sort_order: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MappingTemplateRead(BaseModel):
    id: int
    project_id: int | None
    name: str
    description: str | None = None
    is_global: bool = False
    created_at: datetime
    updated_at: datetime
    fields: list[MappingFieldRead] = []

    model_config = ConfigDict(from_attributes=True)


class MatchedTemplate(BaseModel):
    id: int
    name: str
    description: str | None = None
    match_score: float
    hit_field_count: int = 0
    missing_field_count: int = 0
    possible_mismatch_fields: list[str] = []
    field_structure: dict | None = None
    fields: list[FieldMapping]
    # 是否为 sheet_name + header_hash 精确命中——前端用来显示「一键复用」按钮
    is_exact_match: bool = False
    match_reason: str | None = None


class MappingValidationIssue(BaseModel):
    level: str
    code: str
    message: str
    excel_column_name: str | None = None
    system_field_name: str | None = None


class MappingValidationRequest(BaseModel):
    field_mappings: list[FieldMapping]


class MappingValidationResponse(BaseModel):
    valid: bool
    issues: list[MappingValidationIssue]
