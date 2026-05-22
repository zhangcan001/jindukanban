from datetime import date, datetime

from pydantic import BaseModel


class ReportConfig(BaseModel):
    include_advanced_chart_analysis: bool = True
    use_ai_weekly_text: bool = False
    weekly_delayed_item_limit: int = 30
    weekly_matrix_summary_limit: int = 10
    show_data_quality_section: bool = True
    show_rectification_summary: bool = True
    default_export_format: str = "xlsx"
    file_name_include_project_name: bool = True
    file_name_include_data_date: bool = True


class ReportPreviewResponse(BaseModel):
    report_type: str
    title: str
    items: list[dict[str, str | int | bool | list[str] | None]]


class ReportExportRead(BaseModel):
    id: int
    project_id: int
    batch_id: int | None = None
    report_type: str
    file_name: str | None = None
    file_path: str | None = None
    data_date: date | None = None
    exported_by: str | None = None
    exported_at: datetime

    model_config = {"from_attributes": True}
