from pydantic import BaseModel, Field
from datetime import date

from app.schemas.mapping import FieldMapping
from app.schemas.validation import DataQualityScoreRead, ImportValidationIssueRead, ValidationIssueCodeCount


class ImportConfirmRequest(BaseModel):
    template_name: str | None = None
    save_as_template: bool = False
    data_date: date | None = None
    calculation_profile_id: int | None = None
    baseline_plan_id: int | None = None
    mapping_template_id: int | None = None
    sheet_name: str | None = None
    import_strategy: str = Field("new_batch", pattern="^(new_batch|replace_same_date|overwrite_current)$")
    field_mappings: list[FieldMapping]


class ImportConfirmResponse(BaseModel):
    valid: bool
    status: str
    imported_count: int
    skipped_count: int
    task_created_count: int
    task_matched_count: int
    raw_row_count: int
    template_id: int | None = None
    warning_count: int
    error_count: int
    data_quality: DataQualityScoreRead
    issues: list[ImportValidationIssueRead]
    issue_code_counts: list[ValidationIssueCodeCount] = []


class MultiSheetConfirmSheetRequest(BaseModel):
    batch_id: int
    sheet_name: str
    mappings: list[FieldMapping]
    import_strategy: str = Field("new_batch", pattern="^(new_batch|replace_same_date|overwrite_current)$")
    save_template: bool = False
    template_name: str | None = None
    mapping_template_id: int | None = None


class MultiSheetConfirmRequest(BaseModel):
    project_id: int
    data_date: date | None = None
    baseline_plan_id: int | None = None
    calculation_profile_id: int | None = None
    sheets: list[MultiSheetConfirmSheetRequest]


class MultiSheetConfirmBatchResult(BaseModel):
    sheet_name: str
    batch_id: int | None = None
    imported_count: int = 0
    skipped_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    status: str
    error: str | None = None


class MultiSheetConfirmResponse(BaseModel):
    total_sheets: int
    success_count: int
    failed_count: int
    batches: list[MultiSheetConfirmBatchResult]
