from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.mapping import MatchedTemplate


class ImportBatchRead(BaseModel):
    id: int
    project_id: int
    file_name: str
    file_path: str | None = None
    sheet_name: str | None = None
    import_group_id: str | None = None
    import_group_name: str | None = None
    is_multi_sheet: bool = False
    group_sheet_count: int = 1
    is_frozen: bool = False
    frozen_at: datetime | None = None
    freeze_remark: str | None = None
    data_date: date | None = None
    header_row_index: int | None = None
    data_start_row_index: int | None = None
    multi_header: bool = False
    header_end_row_index: int | None = None
    row_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    imported_count: int = 0
    skipped_count: int = 0
    data_quality_score: float | None = None
    field_completeness: float | None = None
    task_match_rate: float | None = None
    valid_row_rate: float | None = None
    plan_field_completeness: float | None = None
    unit_consistency: float | None = None
    status: str = "draft"
    calculation_profile_id: int | None = None
    baseline_plan_id: int | None = None
    baseline_plan_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImportUploadResponse(BaseModel):
    batch: ImportBatchRead
    sheets: list[str]


class ImportParseRequest(BaseModel):
    sheet_name: str
    data_date: date | None = None
    header_row_index: Optional[int] = Field(default=None, ge=1)
    data_start_row_index: Optional[int] = Field(default=None, ge=1)
    multi_header: bool = False
    header_end_row_index: Optional[int] = Field(default=None, ge=1)


class ParsedColumn(BaseModel):
    name: str
    field_type: str
    recommended_field: str | None = None
    is_dimension: bool = False
    is_metric: bool = False
    save_to_extra: bool = True
    match_type: str | None = None
    confidence: str | None = None
    reason: str | None = None
    field_role: str | None = None
    is_required: bool = False
    affects_statistics: bool = False
    affects_delay: bool = False
    alias_source: str | None = None
    alias_confidence: float | None = None
    needs_review: bool = False


class HeaderRecommendation(BaseModel):
    header_row_index: int | None = None
    data_start_row_index: int | None = None
    confidence: str = "低"


class ImportParseResponse(BaseModel):
    batch: ImportBatchRead
    columns: list[ParsedColumn]
    preview_rows: list[dict[str, Any]]
    matched_templates: list[MatchedTemplate] = []
    header_recommendation: HeaderRecommendation | None = None
    field_diagnostics: dict[str, Any] | None = None


class MultiSheetParseRequest(BaseModel):
    project_id: int
    sheet_names: list[str]
    header_row_index: Optional[int] = Field(default=None, ge=1)
    data_start_row_index: Optional[int] = Field(default=None, ge=1)
    data_date: date | None = None
    baseline_plan_id: int | None = None
    multi_header: bool = False
    header_end_row_index: Optional[int] = Field(default=None, ge=1)


class MultiSheetParseResult(BaseModel):
    sheet_name: str
    status: str
    batch_id: int | None = None
    columns: list[ParsedColumn] = []
    preview_rows: list[dict[str, Any]] = []
    suggested_mappings: list[MatchedTemplate] = []
    warning: str | None = None
    error: str | None = None
    header_row_index: int | None = None
    data_start_row_index: int | None = None
    header_recommendation: HeaderRecommendation | None = None
    row_count: int = 0


class MultiSheetParseResponse(BaseModel):
    import_group_id: str | None = None
    import_group_name: str | None = None
    file_id: int
    project_id: int
    total_sheets: int
    success_count: int
    failed_count: int
    results: list[MultiSheetParseResult]
