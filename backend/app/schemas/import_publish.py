from datetime import datetime

from pydantic import BaseModel


class ImportPublishResponse(BaseModel):
    id: int
    project_id: int
    status: str
    is_active: bool
    imported_count: int
    warning_count: int
    error_count: int
    data_quality_score: float | None = None
    published_by: str | None = None
    published_at: datetime


class MultiSheetPublishResult(BaseModel):
    batch_id: int
    sheet_name: str | None = None
    status: str
    published: bool
    error: str | None = None
    result: ImportPublishResponse | None = None


class MultiSheetPublishResponse(BaseModel):
    total_count: int
    published_count: int
    failed_publish_count: int
    results: list[MultiSheetPublishResult]
