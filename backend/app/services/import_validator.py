from __future__ import annotations

import math
from typing import Any

from app.schemas.mapping import FieldMapping
from app.schemas.validation import ImportValidationIssueRead
from app.services.field_mapping_validator import validate_field_mappings
from app.services.value_normalizer import NORMALIZED_FIELDS, normalize_value
from app.utils.date_utils import is_empty_date_value, normalize_date
from app.utils.number_utils import normalize_percent

NUMBER_FIELDS = {
    "total_quantity",
    "planned_quantity",
    "period_quantity",
    "cumulative_quantity",
    "actual_quantity",
    "remaining_quantity",
    "weight",
    "value_amount",
}

PERCENT_FIELDS = {
    "planned_percent",
    "actual_percent",
    "reported_percent",
    "time_planned_percent",
    "current_period_percent",
}

DATE_FIELDS = {
    "planned_start_date",
    "planned_finish_date",
    "actual_start_date",
    "actual_finish_date",
}

PROGRESS_INDICATOR_FIELDS = {
    "total_quantity",
    "cumulative_quantity",
    "actual_quantity",
    "actual_percent",
    "reported_percent",
    "planned_percent",
    "planned_quantity",
    "period_quantity",
    "current_period_percent",
}

REQUIRED_SYSTEM_FIELDS = {"task_name"}
SUMMARY_ROW_MARKER = "__skip_import"
SUMMARY_ROW_CODE = "SUMMARY_ROW_SKIPPED"
SUMMARY_KEYWORDS = {
    "合计",
    "小计",
    "总计",
    "汇总",
    "总合计",
    "本页合计",
    "本周合计",
    "本月合计",
    "专业小计",
    "区域小计",
    "单位工程小计",
}
SUMMARY_FIELDS = {
    "task_name",
    "parent_task_name",
    "area",
    "building",
    "floor",
    "discipline",
    "system_name",
    "remark",
}


def validate_import_rows(
    raw_rows: list[dict[str, Any]],
    field_mappings: list[FieldMapping],
) -> tuple[list[ImportValidationIssueRead], list[dict[str, Any]]]:
    issues: list[ImportValidationIssueRead] = [
        ImportValidationIssueRead(
            row_index=None,
            column_name=issue.excel_column_name,
            level=issue.level,
            code=issue.code,
            message=issue.message,
        )
        for issue in validate_field_mappings(field_mappings)
    ]

    mapped_fields = {mapping.system_field_name for mapping in field_mappings if mapping.system_field_name}
    for required_field in REQUIRED_SYSTEM_FIELDS:
        if required_field not in mapped_fields:
            issues.append(
                ImportValidationIssueRead(
                    level="error",
                    code="required_field_missing",
                    message=f"必填系统字段 {required_field} 未映射。",
                )
            )

    normalized_rows: list[dict[str, Any]] = []
    active_mappings = [mapping for mapping in field_mappings if mapping.system_field_name]
    for index, row in enumerate(raw_rows, start=1):
        normalized: dict[str, Any] = {}
        row_has_blocking_error = False
        for mapping in active_mappings:
            system_field = mapping.system_field_name or ""
            raw_value = row.get(mapping.excel_column_name)
            value = normalize_value(system_field, raw_value) if system_field in NORMALIZED_FIELDS else raw_value
            normalized[system_field] = value

            if system_field in NUMBER_FIELDS:
                number_value = parse_number(value)
                if number_value is None and has_value(value):
                    issues.append(_issue(index, mapping.excel_column_name, "error", "invalid_number", "数值字段无法解析。"))
                    row_has_blocking_error = True
                elif number_value is not None and system_field in {"total_quantity", "planned_quantity", "actual_quantity", "cumulative_quantity"} and number_value < 0:
                    issues.append(_issue(index, mapping.excel_column_name, "error", "negative_quantity", "工程量字段不能为负数。"))
                    row_has_blocking_error = True

            if system_field in PERCENT_FIELDS:
                percent_value = parse_percent(value)
                if percent_value is None and has_value(value):
                    issues.append(_issue(index, mapping.excel_column_name, "error", "invalid_percent", "百分比字段无法解析。"))
                    row_has_blocking_error = True
                elif percent_value is not None and (percent_value < 0 or percent_value > 100):
                    issues.append(_issue(index, mapping.excel_column_name, "warning", "percent_out_of_range", "百分比不在 0-100 范围内。"))

            if system_field in DATE_FIELDS and not is_empty_date_value(value) and normalize_date(value) is None:
                issues.append(
                    _issue(
                        index,
                        mapping.excel_column_name,
                        "warning",
                        "INVALID_DATE",
                        f"日期格式可能不正确：{value}",
                    )
                )

        if is_summary_row(row, normalized):
            normalized[SUMMARY_ROW_MARKER] = True
            issues.append(_issue(index, None, "warning", SUMMARY_ROW_CODE, "汇总行已跳过。"))
            normalized_rows.append(normalized)
            continue

        if not has_progress_indicator(normalized):
            normalized[SUMMARY_ROW_MARKER] = True
            issues.append(_issue(index, None, "warning", "NO_PROGRESS_METRICS", "缺少可计算进度指标，已跳过。"))
            normalized_rows.append(normalized)
            continue

        total_quantity = parse_number(normalized.get("total_quantity"))
        actual_quantity = parse_number(normalized.get("actual_quantity") or normalized.get("cumulative_quantity"))
        if total_quantity is not None and actual_quantity is not None and total_quantity >= 0 and actual_quantity > total_quantity:
            issues.append(_issue(index, None, "warning", "actual_exceeds_total", "累计/实际完成量大于总工程量。"))
        if not has_value(normalized.get("planned_start_date")):
            issues.append(_issue(index, None, "warning", "planned_start_date_missing", "缺少计划开始时间，无法按计划日期判断应完成进度。"))
        if not has_value(normalized.get("planned_finish_date")):
            issues.append(_issue(index, None, "warning", "planned_finish_date_missing", "缺少计划完成时间，无法按计划日期判断应完成进度。"))
        planned_start = normalize_date(normalized.get("planned_start_date"))
        planned_finish = normalize_date(normalized.get("planned_finish_date"))
        if planned_start is not None and planned_finish is not None and planned_finish < planned_start:
            issues.append(_issue(index, None, "error", "invalid_plan_date_range", "计划完成时间早于计划开始时间。"))
            row_has_blocking_error = True
        if total_quantity is None:
            issues.append(_issue(index, None, "warning", "total_quantity_missing", "缺少总工程量，实际完成率将无法优先按工程量计算。"))
        if not has_value(normalized.get("cumulative_quantity")) and not has_value(normalized.get("actual_quantity")):
            issues.append(_issue(index, None, "warning", "cumulative_quantity_missing", "缺少累计/实际完成量，实际完成率将回退使用导入完成率。"))

        if not has_value(normalized.get("task_name")):
            issues.append(_issue(index, None, "error", "task_name_empty", "任务名称不能为空。"))
            row_has_blocking_error = True

        if row_has_blocking_error:
            normalized[SUMMARY_ROW_MARKER] = True

        normalized_rows.append(normalized)

    return issues, normalized_rows


ABNORMAL_PREVIEW_TYPES = [
    ("日期异常", {"INVALID_DATE"}),
    ("负数工程量", {"negative_quantity"}),
    ("完成率超范围", {"percent_out_of_range", "invalid_percent"}),
    ("必填字段缺失", {"required_field_missing", "task_name_empty"}),
    ("汇总行跳过", {SUMMARY_ROW_CODE}),
    ("单位混杂", {"UNIT_MIXED", "unit_mixed"}),
]


def build_abnormal_preview(
    raw_rows: list[dict[str, Any]],
    issues: list[ImportValidationIssueRead],
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for type_name, codes in ABNORMAL_PREVIEW_TYPES:
        matched = [issue for issue in issues if (issue.code or "") in codes]
        if not matched:
            continue
        examples = []
        for issue in matched[:10]:
            examples.append(
                {
                    "row_index": issue.row_index,
                    "column_name": issue.column_name,
                    "raw_value": _raw_issue_value(raw_rows, issue),
                    "message": issue.message,
                    "level": issue.level,
                    "code": issue.code,
                }
            )
        level = "error" if any(issue.level == "error" for issue in matched) else "warning"
        groups.append({"type": type_name, "level": level, "count": len(matched), "examples": examples})
    return groups


def is_summary_row(row: dict[str, Any], mapped_item: dict[str, Any] | None = None) -> bool:
    mapped_item = mapped_item or {}
    mapped_texts = [_clean_summary_text(mapped_item.get(field)) for field in SUMMARY_FIELDS if has_value(mapped_item.get(field))]
    raw_texts = _first_raw_text_values(row, limit=5)

    if any(text in SUMMARY_KEYWORDS for text in mapped_texts):
        return True

    sparse_row = _is_sparse_summary_shape(row, mapped_item)
    if sparse_row and any(_contains_summary_keyword(text) for text in mapped_texts + raw_texts):
        return True

    return False


def parse_number(value: Any) -> float | None:
    if not has_value(value):
        return None
    if isinstance(value, int | float):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    text = str(value).strip().replace(",", "")
    if text.endswith("%"):
        text = text[:-1]
    try:
        return float(text)
    except ValueError:
        return None


def parse_percent(value: Any) -> float | None:
    return normalize_percent(value)


def looks_like_date(value: Any) -> bool:
    return normalize_date(value) is not None


def has_value(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def should_skip_import(row: dict[str, Any]) -> bool:
    return bool(row.get(SUMMARY_ROW_MARKER))


def has_progress_indicator(row: dict[str, Any]) -> bool:
    return any(has_value(row.get(field)) for field in PROGRESS_INDICATOR_FIELDS)


def _clean_summary_text(value: Any) -> str:
    if not has_value(value):
        return ""
    return str(value).replace(" ", "").replace("\u3000", "").strip().lower()


def _contains_summary_keyword(text: str) -> bool:
    return any(keyword in text for keyword in SUMMARY_KEYWORDS)


def _first_raw_text_values(row: dict[str, Any], limit: int) -> list[str]:
    values: list[str] = []
    for value in row.values():
        if not has_value(value):
            continue
        text = str(value).strip()
        if not text:
            continue
        if parse_number(text) is not None or parse_percent(text) is not None:
            continue
        values.append(_clean_summary_text(text))
        if len(values) >= limit:
            break
    return values


def _is_sparse_summary_shape(row: dict[str, Any], mapped_item: dict[str, Any]) -> bool:
    text_values = [value for value in row.values() if has_value(value) and parse_number(value) is None and parse_percent(value) is None]
    filled_dimensions = [
        field
        for field in ("area", "building", "floor", "discipline", "system_name", "unit")
        if has_value(mapped_item.get(field))
    ]
    task_name = _clean_summary_text(mapped_item.get("task_name"))
    if task_name in SUMMARY_KEYWORDS:
        return True
    return len(text_values) <= 3 and len(filled_dimensions) <= 1


def _issue(row_index: int, column_name: str | None, level: str, code: str, message: str) -> ImportValidationIssueRead:
    return ImportValidationIssueRead(
        row_index=row_index,
        column_name=column_name,
        level=level,
        code=code,
        message=message,
    )


def _raw_issue_value(raw_rows: list[dict[str, Any]], issue: ImportValidationIssueRead) -> Any:
    if issue.row_index is None or issue.row_index < 1 or issue.row_index > len(raw_rows):
        return None
    row = raw_rows[issue.row_index - 1]
    if issue.column_name:
        return row.get(issue.column_name)
    for value in row.values():
        if has_value(value):
            return value
    return None
