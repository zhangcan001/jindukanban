from __future__ import annotations

import json

from app.schemas.report import ReportConfig


DASHBOARD_EXCEL_TYPE = "dashboard_excel"
WEEKLY_WORD_TYPE = "weekly_word"
WEEKLY_PDF_TYPE = "weekly_pdf"
DELAY_RECTIFICATION_EXCEL_TYPE = "delay_rectification_excel"

REPORT_TYPES = {
    "overview": {"label": "进度总览报表", "extension": "xlsx"},
    "delayed-ranking": {"label": "滞后项报表", "extension": "xlsx"},
    "discipline-summary": {"label": "专业进度报表", "extension": "xlsx"},
    "progress-items": {"label": "进度明细报表", "extension": "xlsx"},
    DASHBOARD_EXCEL_TYPE: {"label": "当前看板 Excel", "extension": "xlsx"},
    WEEKLY_WORD_TYPE: {"label": "Word 周报", "extension": "docx"},
    WEEKLY_PDF_TYPE: {"label": "PDF 周报", "extension": "pdf"},
    DELAY_RECTIFICATION_EXCEL_TYPE: {"label": "滞后项整改清单", "extension": "xlsx"},
}

STANDARD_EXCEL_REPORT_TYPES = {"overview", "delayed-ranking", "discipline-summary", "progress-items"}


def resolve_report_config(raw_config: str | None) -> ReportConfig:
    if not raw_config:
        return ReportConfig()
    try:
        parsed = json.loads(raw_config)
    except json.JSONDecodeError:
        return ReportConfig()
    if not isinstance(parsed, dict):
        return ReportConfig()
    aliases = {
        "include_dashboard_plus": "include_advanced_chart_analysis",
        "include_advanced_analysis": "include_advanced_chart_analysis",
        "delayed_item_limit": "weekly_delayed_item_limit",
        "matrix_summary_limit": "weekly_matrix_summary_limit",
        "show_quality_section": "show_data_quality_section",
        "show_rectification": "show_rectification_summary",
    }
    normalized = dict(parsed)
    for old_key, new_key in aliases.items():
        if old_key in normalized and new_key not in normalized:
            normalized[new_key] = normalized[old_key]
    for key in ("weekly_delayed_item_limit", "weekly_matrix_summary_limit"):
        try:
            normalized[key] = max(0, int(normalized.get(key, ReportConfig().model_dump()[key])))
        except (TypeError, ValueError):
            normalized.pop(key, None)
    if normalized.get("default_export_format") not in {"xlsx", "docx"}:
        normalized["default_export_format"] = "xlsx"
    return ReportConfig.model_validate(normalized)


def serialize_report_config(config: ReportConfig) -> str:
    return json.dumps(config.model_dump(), ensure_ascii=False)
