from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.progress_task import ProgressTask
from app.schemas.mapping import FieldMapping
from app.schemas.validation import DataQualityScoreRead, ImportValidationIssueRead
from app.services.import_validator import has_value

CORE_FIELDS = {
    "task_name",
    "area",
    "building",
    "floor",
    "discipline",
    "system_name",
    "unit",
    "total_quantity",
}

PLAN_FIELDS = {
    "planned_quantity",
    "planned_percent",
    "planned_start_date",
    "planned_finish_date",
}

TASK_IDENTITY_FIELDS = {
    "identity_key",
    "wbs_code",
    "task_code",
    "task_name",
}


def calculate_data_quality_score(
    db: Session,
    project_id: int,
    normalized_rows: list[dict[str, Any]],
    field_mappings: list[FieldMapping],
    issues: list[ImportValidationIssueRead],
) -> DataQualityScoreRead:
    row_count = len(normalized_rows)
    if row_count == 0:
        return DataQualityScoreRead(
            data_quality_score=0,
            field_completeness=0,
            task_match_rate=0,
            valid_row_rate=0,
            plan_field_completeness=0,
            unit_consistency=0,
        )

    mapped_fields = {mapping.system_field_name for mapping in field_mappings if mapping.system_field_name}

    field_completeness = _calculate_field_completeness(normalized_rows, mapped_fields)
    task_match_rate = _calculate_task_match_rate(db, project_id, normalized_rows)
    valid_row_rate = _calculate_valid_row_rate(row_count, issues)
    plan_field_completeness = _calculate_plan_field_completeness(normalized_rows, mapped_fields)
    unit_consistency = _calculate_unit_consistency(normalized_rows, mapped_fields)

    score = (
        field_completeness * 25
        + task_match_rate * 20
        + valid_row_rate * 25
        + plan_field_completeness * 15
        + unit_consistency * 15
    )

    return DataQualityScoreRead(
        data_quality_score=round(_clamp(score, 0, 100), 2),
        field_completeness=round(field_completeness, 4),
        task_match_rate=round(task_match_rate, 4),
        valid_row_rate=round(valid_row_rate, 4),
        plan_field_completeness=round(plan_field_completeness, 4),
        unit_consistency=round(unit_consistency, 4),
    )


def _calculate_field_completeness(normalized_rows: list[dict[str, Any]], mapped_fields: set[str | None]) -> float:
    expected_fields = CORE_FIELDS
    filled = 0
    possible = len(expected_fields) * len(normalized_rows)
    if possible == 0:
        return 0

    for row in normalized_rows:
        for field in expected_fields:
            if field in mapped_fields and has_value(row.get(field)):
                filled += 1

    return _ratio(filled, possible)


def _calculate_task_match_rate(db: Session, project_id: int, normalized_rows: list[dict[str, Any]]) -> float:
    task_keys = _load_existing_task_keys(db, project_id)
    identifiable_count = 0
    matched_count = 0

    for row in normalized_rows:
        row_keys = _row_task_keys(row)
        if row_keys:
            identifiable_count += 1
        if task_keys and row_keys.intersection(task_keys):
            matched_count += 1

    if task_keys:
        return _ratio(matched_count, len(normalized_rows))

    # Before the formal import phase creates progress_task rows, use identity readiness
    # as the MVP fallback so fresh projects are not scored as an automatic zero.
    return _ratio(identifiable_count, len(normalized_rows))


def _calculate_valid_row_rate(row_count: int, issues: list[ImportValidationIssueRead]) -> float:
    if any(issue.level == "error" and issue.row_index is None for issue in issues):
        return 0
    invalid_rows = {issue.row_index for issue in issues if issue.level == "error" and issue.row_index is not None}
    return _ratio(row_count - len(invalid_rows), row_count)


def _calculate_plan_field_completeness(normalized_rows: list[dict[str, Any]], mapped_fields: set[str | None]) -> float:
    possible = len(PLAN_FIELDS) * len(normalized_rows)
    if possible == 0:
        return 0

    filled = 0
    for row in normalized_rows:
        for field in PLAN_FIELDS:
            if field in mapped_fields and has_value(row.get(field)):
                filled += 1

    return _ratio(filled, possible)


def _calculate_unit_consistency(normalized_rows: list[dict[str, Any]], mapped_fields: set[str | None]) -> float:
    if "unit" not in mapped_fields:
        return 0

    unit_groups: dict[str, list[str]] = defaultdict(list)
    missing_unit_count = 0
    for row in normalized_rows:
        unit = _normalize_text(row.get("unit"))
        if not unit:
            missing_unit_count += 1
            continue
        task_key = _primary_task_key(row) or "__all__"
        unit_groups[task_key].append(unit)

    consistent_count = 0
    for units in unit_groups.values():
        most_common_count = Counter(units).most_common(1)[0][1]
        consistent_count += most_common_count

    return _ratio(consistent_count, consistent_count + sum(len(units) - Counter(units).most_common(1)[0][1] for units in unit_groups.values()) + missing_unit_count)


def _load_existing_task_keys(db: Session, project_id: int) -> set[str]:
    tasks = db.execute(
        select(ProgressTask).where(ProgressTask.project_id == project_id, ProgressTask.is_active.is_(True))
    ).scalars()
    keys: set[str] = set()
    for task in tasks:
        for value in (task.identity_key, task.wbs_code, task.task_code, task.normalized_task_name, task.task_name):
            normalized = _normalize_text(value)
            if normalized:
                keys.add(normalized)
    return keys


def _row_task_keys(row: dict[str, Any]) -> set[str]:
    keys = {_normalize_text(row.get(field)) for field in TASK_IDENTITY_FIELDS}
    return {key for key in keys if key}


def _primary_task_key(row: dict[str, Any]) -> str | None:
    for field in ("identity_key", "wbs_code", "task_code", "task_name"):
        normalized = _normalize_text(row.get(field))
        if normalized:
            return normalized
    return None


def _normalize_text(value: Any) -> str:
    if not has_value(value):
        return ""
    return str(value).strip().lower()


def _ratio(numerator: int | float, denominator: int | float) -> float:
    if denominator <= 0:
        return 0
    return _clamp(float(numerator) / float(denominator), 0, 1)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
