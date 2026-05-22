from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy.orm import Session

from app.models.progress_item import ProgressItem
from app.schemas.analytics import (
    DashboardPlusBuildingDisciplineCell,
    DashboardPlusDelayDistribution,
    DashboardPlusDelayStatusCount,
    DashboardPlusDisciplineDelayCount,
    DashboardPlusDisciplineProgressRow,
    DashboardPlusFloorDisciplineCell,
    DashboardPlusResponse,
    DashboardPlusTaskDetail,
)
from app.services.analytics_service import (
    aggregate_progress,
    apply_time_based_progress,
    delayed_count,
    delay_reference_date,
    display_text,
    effective_baseline_plan,
    filter_items_by_baseline,
    get_published_batch,
    group_items,
    is_delay_eligible,
    item_units,
    list_items,
    resolve_calculation_profile,
    sort_dimension_value,
)
from app.services.progress_calculator import (
    DEFAULT_DELAY_THRESHOLDS,
    DelayThresholds,
    classify_delay_status,
)

DELAY_STATUS_LABELS = {
    "seriously_delayed": "严重滞后",
    "delayed": "明显滞后",
    "slightly_delayed": "轻微滞后",
    "normal": "正常",
    "ahead": "超前",
    "not_started_by_plan": "未到计划开始",
    "missing_plan_dates": "缺少计划日期",
    "invalid_plan_dates": "计划日期异常",
    "unknown": "未知",
}
DELAY_STATUS_ORDER = [
    "seriously_delayed",
    "delayed",
    "slightly_delayed",
    "normal",
    "ahead",
    "not_started_by_plan",
    "missing_plan_dates",
    "invalid_plan_dates",
    "unknown",
]


def build_dashboard_plus(
    db: Session,
    project_id: int,
    batch_id: int | None = None,
    calculation_profile_id: int | None = None,
    calculation_method: str | None = None,
    baseline_plan_id: int | None = None,
    building: str | None = None,
    discipline: str | None = None,
    floor: str | None = None,
    construction_unit: str | None = None,
    system_name: str | None = None,
    delay_level: str | None = None,
    metric: str | None = None,
) -> DashboardPlusResponse:
    filters = _clean_filters(building, discipline, floor, delay_level, metric, construction_unit, system_name)
    batch = get_published_batch(db, project_id, batch_id)
    if batch is None:
        return DashboardPlusResponse(batch_id=None, filters=filters)

    profile = resolve_calculation_profile(db, project_id, calculation_profile_id or batch.calculation_profile_id)
    baseline = effective_baseline_plan(db, project_id, batch, baseline_plan_id)
    all_items = filter_items_by_baseline(apply_time_based_progress(list_items(db, project_id, batch.id), batch, profile), baseline)
    reference_date = delay_reference_date(batch)
    has_floor_data = any((item.floor or "").strip() for item in all_items)
    has_building_data = any((item.building or "").strip() for item in all_items)
    items = _apply_filters(all_items, filters, reference_date)
    algorithm = calculation_method or (profile.group_algorithm if profile else "auto") or "auto"

    return DashboardPlusResponse(
        batch_id=batch.id,
        filters=filters,
        has_floor_data=has_floor_data,
        has_building_data=has_building_data,
        discipline_progress=_discipline_progress(items, profile, algorithm, reference_date),
        floor_discipline_matrix=_floor_discipline_matrix(items, profile, algorithm, reference_date),
        building_discipline_matrix=_building_discipline_matrix(items, profile, algorithm, reference_date),
        delay_distribution=_delay_distribution(items, reference_date),
        task_details=_task_details(items, reference_date),
    )


def _discipline_progress(items: list[ProgressItem], profile, algorithm: str, reference_date) -> list[DashboardPlusDisciplineProgressRow]:
    rows: list[DashboardPlusDisciplineProgressRow] = []
    for discipline, group in group_items(items, "discipline").items():
        actual_percent, actual_unit_mixed, actual_warning = aggregate_progress(group, profile, "actual_percent", algorithm)
        planned_percent, planned_unit_mixed, planned_warning = aggregate_progress(group, profile, "planned_percent", algorithm)
        deviation = _deviation(actual_percent, planned_percent)
        seriously_delayed_count = sum(1 for item in group if _delay_status(item, reference_date) == "seriously_delayed")
        rows.append(
            DashboardPlusDisciplineProgressRow(
                discipline=display_text(discipline, "未填写专业"),
                task_count=len(group),
                actual_percent=actual_percent,
                planned_percent=planned_percent,
                progress_deviation=deviation,
                delayed_count=delayed_count(group, reference_date),
                seriously_delayed_count=seriously_delayed_count,
                is_seriously_delayed=seriously_delayed_count > 0 or (deviation is not None and deviation <= -10),
                unit_mixed=actual_unit_mixed or planned_unit_mixed,
                units=item_units(group),
                warning=actual_warning or planned_warning,
            )
        )
    rows.sort(key=lambda row: sort_dimension_value("discipline", row.discipline))
    return rows


def _floor_discipline_matrix(items: list[ProgressItem], profile, algorithm: str, reference_date) -> list[DashboardPlusFloorDisciplineCell]:
    groups: dict[tuple[str, str], list[ProgressItem]] = defaultdict(list)
    for item in items:
        groups[(display_text(item.floor, "未填写楼层"), display_text(item.discipline, "未填写专业"))].append(item)
    rows: list[DashboardPlusFloorDisciplineCell] = []
    for (floor, discipline), group in groups.items():
        actual_percent, _, _ = aggregate_progress(group, profile, "actual_percent", algorithm)
        planned_percent, _, _ = aggregate_progress(group, profile, "planned_percent", algorithm)
        rows.append(
            DashboardPlusFloorDisciplineCell(
                floor=floor,
                discipline=discipline,
                task_count=len(group),
                actual_percent=actual_percent,
                progress_deviation=_deviation(actual_percent, planned_percent),
                delayed_count=delayed_count(group, reference_date),
            )
        )
    rows.sort(key=lambda row: (sort_dimension_value("floor", row.floor), sort_dimension_value("discipline", row.discipline)))
    return rows


def _building_discipline_matrix(items: list[ProgressItem], profile, algorithm: str, reference_date) -> list[DashboardPlusBuildingDisciplineCell]:
    groups: dict[tuple[str, str], list[ProgressItem]] = defaultdict(list)
    for item in items:
        groups[(display_text(item.building, "未填写楼栋"), display_text(item.discipline, "未填写专业"))].append(item)
    rows: list[DashboardPlusBuildingDisciplineCell] = []
    for (building, discipline), group in groups.items():
        actual_percent, _, _ = aggregate_progress(group, profile, "actual_percent", algorithm)
        rows.append(
            DashboardPlusBuildingDisciplineCell(
                building=building,
                discipline=discipline,
                task_count=len(group),
                actual_percent=actual_percent,
                delayed_count=delayed_count(group, reference_date),
            )
        )
    rows.sort(key=lambda row: (sort_dimension_value("building", row.building), sort_dimension_value("discipline", row.discipline)))
    return rows


def _delay_distribution(items: list[ProgressItem], reference_date) -> DashboardPlusDelayDistribution:
    status_counter = Counter(_delay_status(item, reference_date) for item in items)
    discipline_counters: dict[str, Counter[str]] = defaultdict(Counter)
    for item in items:
        discipline = display_text(item.discipline, "未填写专业")
        discipline_counters[discipline][_delay_status(item, reference_date)] += 1
    return DashboardPlusDelayDistribution(
        status_counts=[
            DashboardPlusDelayStatusCount(status=status, status_label=DELAY_STATUS_LABELS[status], count=status_counter[status])
            for status in DELAY_STATUS_ORDER
        ],
        discipline_delay_counts=[
            DashboardPlusDisciplineDelayCount(
                discipline=discipline,
                seriously_delayed_count=counter["seriously_delayed"],
                delayed_count=counter["delayed"],
                slightly_delayed_count=counter["slightly_delayed"],
                normal_count=counter["normal"],
                ahead_count=counter["ahead"],
                total_delayed_count=counter["seriously_delayed"] + counter["delayed"] + counter["slightly_delayed"],
            )
            for discipline, counter in sorted(discipline_counters.items(), key=lambda row: sort_dimension_value("discipline", row[0]))
        ],
    )


def _task_details(items: list[ProgressItem], reference_date) -> list[DashboardPlusTaskDetail]:
    rows = [
        DashboardPlusTaskDetail(
            id=item.id,
            construction_unit=getattr(item, "construction_unit", None),
            building=display_text(item.building, "未填写楼栋"),
            floor=display_text(item.floor, "未填写楼层"),
            discipline=display_text(item.discipline, "未填写专业"),
            task_name=display_text(item.task_name, "未填写施工项"),
            actual_percent=item.actual_percent,
            planned_percent=item.planned_percent,
            progress_deviation=item.progress_deviation,
            status=item.status,
            delay_level=_delay_status(item, reference_date),
            delay_level_label=DELAY_STATUS_LABELS[_delay_status(item, reference_date)],
        )
        for item in items
    ]
    rows.sort(key=lambda row: (sort_dimension_value("building", row.building), sort_dimension_value("floor", row.floor), sort_dimension_value("discipline", row.discipline), row.id))
    return rows


def _clean_filters(
    building: str | None,
    discipline: str | None,
    floor: str | None,
    delay_level: str | None,
    metric: str | None,
    construction_unit: str | None = None,
    system_name: str | None = None,
) -> dict[str, str | None]:
    return {
        "construction_unit": _clean_text(construction_unit),
        "building": _clean_text(building),
        "discipline": _clean_text(discipline),
        "floor": _clean_text(floor),
        "system_name": _clean_text(system_name),
        "delay_level": _clean_text(delay_level),
        "metric": _clean_text(metric) or "actual_percent",
    }


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _apply_filters(items: list[ProgressItem], filters: dict[str, str | None], reference_date) -> list[ProgressItem]:
    filtered = items
    if filters.get("construction_unit"):
        filtered = [item for item in filtered if display_text(getattr(item, "construction_unit", None), "未填写施工单位") == filters["construction_unit"]]
    if filters.get("building"):
        filtered = [item for item in filtered if display_text(item.building, "未填写楼栋") == filters["building"]]
    if filters.get("discipline"):
        filtered = [item for item in filtered if display_text(item.discipline, "未填写专业") == filters["discipline"]]
    if filters.get("floor"):
        filtered = [item for item in filtered if display_text(item.floor, "未填写楼层") == filters["floor"]]
    if filters.get("system_name"):
        filtered = [item for item in filtered if display_text(item.system_name, "未填写系统") == filters["system_name"]]
    if filters.get("delay_level"):
        filtered = [item for item in filtered if _delay_status(item, reference_date) == filters["delay_level"]]
    return filtered


def _deviation(actual_percent: float | None, planned_percent: float | None) -> float | None:
    if actual_percent is None or planned_percent is None:
        return None
    return round(actual_percent - planned_percent, 4)


def _delay_status(
    item: ProgressItem,
    reference_date,
    thresholds: DelayThresholds = DEFAULT_DELAY_THRESHOLDS,
) -> str:
    if not is_delay_eligible(item, reference_date):
        if item.status in {"not_started_by_plan", "missing_plan_dates", "invalid_plan_dates"}:
            return item.status
        return "unknown"
    deviation = item.progress_deviation
    if deviation is None:
        return "normal"
    return classify_delay_status(deviation, thresholds)
