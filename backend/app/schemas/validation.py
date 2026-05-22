from typing import Any

from pydantic import BaseModel

from app.schemas.mapping import FieldMapping


class ImportValidationRequest(BaseModel):
    field_mappings: list[FieldMapping]


class ImportValidationIssueRead(BaseModel):
    row_index: int | None = None
    column_name: str | None = None
    level: str
    code: str | None = None
    message: str


class DataQualityScoreRead(BaseModel):
    data_quality_score: float
    field_completeness: float
    task_match_rate: float
    valid_row_rate: float
    plan_field_completeness: float
    unit_consistency: float


class ValidationIssueCodeCount(BaseModel):
    code: str
    level: str
    count: int


class AbnormalPreviewExample(BaseModel):
    row_index: int | None = None
    column_name: str | None = None
    raw_value: Any = None
    message: str
    level: str
    code: str | None = None


class AbnormalPreviewGroup(BaseModel):
    type: str
    level: str
    count: int
    examples: list[AbnormalPreviewExample] = []


def summarize_issue_codes(issues: list[ImportValidationIssueRead]) -> list[ValidationIssueCodeCount]:
    counts: dict[tuple[str, str], int] = {}
    for issue in issues:
        code = issue.code or "UNKNOWN"
        key = (code, issue.level)
        counts[key] = counts.get(key, 0) + 1
    return [
        ValidationIssueCodeCount(code=code, level=level, count=count)
        for (code, level), count in sorted(counts.items(), key=lambda item: (-item[1], item[0][1], item[0][0]))
    ]


class ImportValidationResponse(BaseModel):
    valid: bool
    warning_count: int
    error_count: int
    data_quality: DataQualityScoreRead
    issues: list[ImportValidationIssueRead]
    issue_code_counts: list[ValidationIssueCodeCount] = []
    abnormal_preview: list[AbnormalPreviewGroup] = []
    normalized_preview_rows: list[dict[str, Any]]


class MultiSheetValidationSheetRequest(BaseModel):
    batch_id: int
    sheet_name: str
    mappings: list[FieldMapping]
    header_row_index: int | None = None
    data_start_row_index: int | None = None


class MultiSheetValidationRequest(BaseModel):
    sheets: list[MultiSheetValidationSheetRequest]


class MultiSheetValidationResult(BaseModel):
    sheet_name: str
    batch_id: int
    valid: bool
    warning_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    data_quality_score: float | None = None
    issues: list[ImportValidationIssueRead] = []
    abnormal_preview: list[AbnormalPreviewGroup] = []
    error: str | None = None


class MultiSheetValidationResponse(BaseModel):
    total_sheets: int
    success_count: int
    failed_count: int
    results: list[MultiSheetValidationResult]
