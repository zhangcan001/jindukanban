from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
import json
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.import_batch import ImportBatch
from app.models.progress_item import ProgressItem
from app.models.project import Project
from app.models.rectification_item import RectificationItem
from app.models.warning_record import WarningRecord
from app.schemas.analytics import (
    AnalyticsDelayedItem,
    AnalyticsOverviewResponse,
    AnalyticsWarning,
    DashboardBuildingElevation,
    DashboardBuildingElevationFloor,
    DashboardUnifiedDelayDistributionRow,
    DashboardUnifiedFilters,
    DashboardUnifiedMatrixRow,
    DashboardUnifiedOptions,
    DashboardUnifiedResponse,
    DashboardUnifiedStatRow,
    DashboardUnifiedSummary,
    ProjectOverviewBatch,
)
from app.services.analytics_service import (
    aggregate_progress,
    apply_time_based_progress,
    available_calculation_methods,
    baseline_context,
    build_delay_message,
    calculated_deviation,
    delayed_count,
    delayed_items,
    delay_level_for_deviation,
    delay_reference_date,
    display_text,
    effective_baseline_plan,
    effective_calculation_method,
    filter_items_by_baseline,
    item_units,
    list_items,
    quantity_sum,
    resolve_calculation_profile,
    sort_dimension_value,
    statistics_context,
    status_counts,
)
from app.services.progress_calculator import (
    DEFAULT_DELAY_THRESHOLDS,
    DelayThresholds,
    classify_delay_status,
)

CONSTRUCTION_UNIT_ALIASES = ("施工单位", "分包单位", "责任单位", "单位名称", "承包单位")

DELAY_STATUS_LABELS = {
    "seriously_delayed": "严重滞后",
    "delayed_or_worse": "明显及以上滞后",
    "any_delayed": "全部滞后",
    "delayed": "明显滞后",
    "slightly_delayed": "轻微滞后",
    "normal": "正常",
    "ahead": "超前",
    "not_started_by_plan": "未到计划开始",
    "missing_plan_dates": "缺少计划日期",
    "invalid_plan_dates": "计划日期异常",
    "unknown": "未知",
}
DELAY_STATUS_ORDER = list(DELAY_STATUS_LABELS)


def build_dashboard_unified(
    db: Session,
    project: Project,
    *,
    data_date: date | None = None,
    import_group_id: str | None = None,
    batch_id: int | None = None,
    sheet_name: str | None = None,
    construction_unit: str | None = None,
    building: str | None = None,
    floor: str | None = None,
    discipline: str | None = None,
    system_name: str | None = None,
    status: str | None = None,
    calculation_method: str | None = None,
    baseline_plan_id: int | None = None,
    calculation_profile_id: int | None = None,
) -> DashboardUnifiedResponse:
    batches = _select_batches(db, project.id, data_date, import_group_id, batch_id, sheet_name)
    calculation_method = effective_calculation_method(project, calculation_method)
    filters = DashboardUnifiedFilters(
        project_id=project.id,
        data_date=data_date or (batches[0].data_date if batches and _single_data_date(batches) else None),
        import_group_id=import_group_id,
        batch_id=batch_id,
        sheet_name=sheet_name,
        construction_unit=_clean(construction_unit),
        building=_clean(building),
        floor=_clean(floor),
        discipline=_clean(discipline),
        system_name=_clean(system_name),
        status=_clean(status),
        calculation_method=calculation_method or "auto",
        baseline_plan_id=baseline_plan_id,
        calculation_profile_id=calculation_profile_id,
        scope_label=_scope_label(batches, bool(batch_id), data_date, import_group_id, sheet_name),
        message=None if batches else "当前项目暂无符合筛选条件的已发布数据。",
    )
    if not batches:
        return DashboardUnifiedResponse(filters=filters)

    profile = resolve_calculation_profile(db, project.id, calculation_profile_id or batches[0].calculation_profile_id)
    batch_items: list[tuple[ImportBatch, list[ProgressItem]]] = []
    base_items: list[ProgressItem] = []
    for batch in batches:
        baseline = effective_baseline_plan(db, project.id, batch, baseline_plan_id)
        items = filter_items_by_baseline(
            apply_time_based_progress(list_items(db, project.id, batch.id), batch, profile),
            baseline,
        )
        batch_items.append((batch, items))
        base_items.extend(items)

    reference_date = max((batch.data_date for batch in batches if batch.data_date), default=date.today())
    options = _options(base_items)
    filtered_items = _apply_filters(
        base_items,
        reference_date,
        construction_unit=construction_unit,
        building=building,
        floor=floor,
        discipline=discipline,
        system_name=system_name,
        status=status,
    )
    algorithm = calculation_method or (profile.group_algorithm if profile else "auto") or "auto"
    warnings_by_item = _warning_counts_by_item(db, project.id, [batch.id for batch in batches], filtered_items)
    rectifications_by_item = _rectification_counts_by_item(db, project.id, [batch.id for batch in batches], filtered_items)
    overview = _overview(db, project, batches, filtered_items, batch_items, profile, calculation_method, baseline_plan_id)
    stats_meta = statistics_context(filtered_items, profile, calculation_method)

    return DashboardUnifiedResponse(
        filters=filters,
        options=options,
        overview=overview,
        calculation_context={
            "calculation_method": stats_meta.algorithm,
            "calculation_method_name": stats_meta.label,
            "recommendation_reason": stats_meta.reason,
            "mixed_units": len(item_units(filtered_items)) > 1,
            "weight_source": stats_meta.weight_source,
            "weight_total": stats_meta.weight_total,
            "participating_task_count": len(filtered_items),
        },
        by_construction_unit=_stat_rows(filtered_items, "construction_unit", profile, algorithm, reference_date, warnings_by_item, rectifications_by_item),
        by_building=_stat_rows(filtered_items, "building", profile, algorithm, reference_date, warnings_by_item, rectifications_by_item),
        by_floor=_stat_rows(filtered_items, "floor", profile, algorithm, reference_date, warnings_by_item, rectifications_by_item),
        by_discipline=_stat_rows(filtered_items, "discipline", profile, algorithm, reference_date, warnings_by_item, rectifications_by_item),
        by_system=_stat_rows(filtered_items, "system_name", profile, algorithm, reference_date, warnings_by_item, rectifications_by_item),
        building_floor_matrix=_matrix_rows(filtered_items, ("building", "floor"), profile, algorithm, reference_date),
        building_elevation=_building_elevation_rows(db, project.id, filtered_items, profile, algorithm, reference_date),
        discipline_floor_matrix=_matrix_rows(filtered_items, ("discipline", "floor"), profile, algorithm, reference_date),
        delay_distribution=_delay_distribution(filtered_items, reference_date, stats_meta.algorithm),
        delayed_items=_delayed_item_rows(db, project.id, filtered_items, reference_date),
        warning_summary=_warning_summary(db, project.id, [batch.id for batch in batches], filtered_items, stats_meta.algorithm),
        rectification_summary=_rectification_summary(db, project.id, [batch.id for batch in batches], filtered_items, stats_meta.algorithm),
    )


def _select_batches(
    db: Session,
    project_id: int,
    data_date: date | None,
    import_group_id: str | None,
    batch_id: int | None,
    sheet_name: str | None,
) -> list[ImportBatch]:
    statement = select(ImportBatch).where(
        ImportBatch.project_id == project_id,
        ImportBatch.is_active.is_(True),
        ImportBatch.status == "published",
    )
    if batch_id is not None:
        statement = statement.where(ImportBatch.id == batch_id)
    if data_date is not None:
        statement = statement.where(ImportBatch.data_date == data_date)
    if import_group_id:
        statement = statement.where(ImportBatch.import_group_id == import_group_id)
    if sheet_name:
        statement = statement.where(ImportBatch.sheet_name == sheet_name)
    if batch_id is None and data_date is None:
        latest = db.scalar(
            select(ImportBatch.data_date)
            .where(ImportBatch.project_id == project_id, ImportBatch.is_active.is_(True), ImportBatch.status == "published")
            .order_by(ImportBatch.data_date.is_(None), ImportBatch.data_date.desc(), ImportBatch.created_at.desc())
            .limit(1)
        )
        statement = statement.where(ImportBatch.data_date == latest) if latest is not None else statement.where(ImportBatch.data_date.is_(None))
    return list(db.scalars(statement.order_by(ImportBatch.data_date.asc(), ImportBatch.id.asc())))


def _overview(
    db: Session,
    project: Project,
    batches: list[ImportBatch],
    items: list[ProgressItem],
    batch_items: list[tuple[ImportBatch, list[ProgressItem]]],
    profile,
    calculation_method: str | None,
    baseline_plan_id: int | None,
) -> AnalyticsOverviewResponse:
    actual_percent, unit_mixed, warning = aggregate_progress(items, profile, "actual_percent", calculation_method)
    planned_percent, planned_unit_mixed, planned_warning = aggregate_progress(items, profile, "planned_percent", calculation_method)
    time_planned_percent, _, _ = aggregate_progress(items, profile, "time_planned_percent", calculation_method)
    imported_planned_percent, _, _ = aggregate_progress(items, profile, "imported_planned_percent", calculation_method)
    total_quantity, total_unit_mixed, total_warning = quantity_sum(items, "total_quantity", profile)
    actual_quantity, actual_unit_mixed, actual_warning = quantity_sum(items, "actual_quantity", profile)
    remaining_quantity, remaining_unit_mixed, remaining_warning = quantity_sum(items, "remaining_quantity", profile)
    stats_meta = statistics_context(items, profile, calculation_method)
    methods = available_calculation_methods(items)
    units = item_units(items)
    deviation = round(actual_percent - planned_percent, 4) if actual_percent is not None and planned_percent is not None else None
    warnings = [
        AnalyticsWarning(code="unit_mixed", message=message)
        for message in {warning, planned_warning, total_warning, actual_warning, remaining_warning}
        if message
    ]
    if stats_meta.weight_warning:
        warnings.append(AnalyticsWarning(code="weight_quality", message=stats_meta.weight_warning))
    if items and actual_percent is None:
        warnings.append(AnalyticsWarning(code="no_calculable_actual_progress", message="当前范围缺少可计算的实际进度字段。"))
    if items and planned_percent is None:
        warnings.append(AnalyticsWarning(code="no_calculable_planned_progress", message="当前范围缺少计划进度字段。"))
    baseline_meta = baseline_context(db, project.id, batches[0], baseline_plan_id) if len(batches) == 1 else {}
    included_batches = []
    for batch, source_items in batch_items:
        batch_filtered_ids = {item.id for item in items}
        scoped = [item for item in source_items if item.id in batch_filtered_ids]
        batch_actual, _, _ = aggregate_progress(scoped, profile, "actual_percent", calculation_method)
        batch_planned, _, _ = aggregate_progress(scoped, profile, "planned_percent", calculation_method)
        included_batches.append(
            ProjectOverviewBatch(
                batch_id=batch.id,
                sheet_name=batch.sheet_name,
                import_group_id=batch.import_group_id,
                import_group_name=batch.import_group_name,
                data_date=batch.data_date,
                actual_percent=batch_actual,
                planned_percent=batch_planned,
                item_count=len(scoped),
            )
        )
    return AnalyticsOverviewResponse(
        batch_id=batches[0].id if len(batches) == 1 else None,
        calculation_profile_id=profile.id if profile else None,
        calculation_method=stats_meta.algorithm,
        calculation_method_name=stats_meta.label,
        recommended_method=next((str(method["code"]) for method in methods if method.get("recommended")), None),
        statistics_algorithm=stats_meta.algorithm,
        statistics_label=stats_meta.label,
        weight_source=stats_meta.weight_source,
        weight_count=stats_meta.weight_count,
        weight_total=stats_meta.weight_total,
        is_weight_normalized=stats_meta.is_normalized,
        normalized_actual_progress=actual_percent if stats_meta.is_normalized else None,
        normalized_planned_progress=planned_percent if stats_meta.is_normalized else None,
        project_contribution_actual=stats_meta.project_contribution_actual,
        project_contribution_planned=stats_meta.project_contribution_planned,
        weight_warning=stats_meta.weight_warning,
        recommendation_reason=stats_meta.reason,
        calculation_method_description=stats_meta.method_description,
        available_methods=methods,
        available_calculation_methods=methods,
        mixed_units=len(units) > 1,
        unit_list=units,
        weight_sum=stats_meta.weight_total,
        included_batch_count=len(batches),
        included_batches=included_batches,
        baseline_plan_id=baseline_meta.get("current_view_baseline_plan_id"),
        baseline_plan_name=baseline_meta.get("current_view_baseline_plan_name"),
        batch_bound_baseline_plan_id=baseline_meta.get("batch_bound_baseline_plan_id"),
        batch_bound_baseline_plan_name=baseline_meta.get("batch_bound_baseline_plan_name"),
        current_view_baseline_plan_id=baseline_meta.get("current_view_baseline_plan_id"),
        current_view_baseline_plan_name=baseline_meta.get("current_view_baseline_plan_name"),
        baseline_consistent=bool(baseline_meta.get("baseline_consistent", True)),
        baseline_notice=baseline_meta.get("baseline_notice"),
        item_count=len(items),
        task_count=len({item.task_id for item in items if item.task_id is not None}) or len(items),
        actual_percent=actual_percent,
        planned_percent=planned_percent,
        actual_progress=actual_percent,
        planned_progress=planned_percent,
        time_planned_percent=time_planned_percent,
        imported_planned_percent=imported_planned_percent,
        progress_deviation=deviation,
        total_quantity=total_quantity,
        actual_quantity=actual_quantity,
        remaining_quantity=remaining_quantity,
        status_counts=status_counts(items),
        unit_mixed=unit_mixed or planned_unit_mixed or total_unit_mixed or actual_unit_mixed or remaining_unit_mixed,
        warning=warnings[0].message if warnings else None,
        warnings=warnings,
        batch_status_label="多 Sheet 聚合" if len(batches) > 1 else ("已冻结" if batches[0].is_frozen else "正常"),
        batch_is_frozen=any(batch.is_frozen for batch in batches),
        project_is_archived=project.is_archived,
    )


def _stat_rows(
    items: list[ProgressItem],
    dimension: str,
    profile,
    algorithm: str,
    reference_date: date,
    warnings_by_item: Counter[int],
    rectifications_by_item: Counter[int],
) -> list[DashboardUnifiedStatRow]:
    rows = []
    for value, group in _group_by_dimension(items, dimension).items():
        actual, _, _ = aggregate_progress(group, profile, "actual_percent", algorithm)
        planned, _, _ = aggregate_progress(group, profile, "planned_percent", algorithm)
        deviation = round(actual - planned, 4) if actual is not None and planned is not None else None
        seriously = sum(1 for item in group if _delay_status(item, reference_date) == "seriously_delayed")
        rows.append(
            DashboardUnifiedStatRow(
                name=value,
                construction_unit=value if dimension == "construction_unit" else None,
                building=value if dimension == "building" else None,
                floor=value if dimension == "floor" else None,
                discipline=value if dimension == "discipline" else None,
                system_name=value if dimension == "system_name" else None,
                task_count=len(group),
                actual_percent=actual,
                planned_percent=planned,
                progress_deviation=deviation,
                delayed_count=delayed_count(group, reference_date),
                seriously_delayed_count=seriously,
                warning_count=sum(warnings_by_item[item.id] for item in group if item.id),
                rectification_count=sum(rectifications_by_item[item.id] for item in group if item.id),
                calculation_method=algorithm,
            )
        )
    rows.sort(key=lambda row: sort_dimension_value(dimension, row.name))
    return rows


def _matrix_rows(items: list[ProgressItem], dimensions: tuple[str, str], profile, algorithm: str, reference_date: date) -> list[DashboardUnifiedMatrixRow]:
    groups: dict[tuple[str, str], list[ProgressItem]] = defaultdict(list)
    for item in items:
        groups[(_dimension_value(item, dimensions[0]), _dimension_value(item, dimensions[1]))].append(item)
    rows = []
    for (first, second), group in groups.items():
        actual, _, _ = aggregate_progress(group, profile, "actual_percent", algorithm)
        planned, _, _ = aggregate_progress(group, profile, "planned_percent", algorithm)
        deviation = round(actual - planned, 4) if actual is not None and planned is not None else None
        status_counter = Counter(_delay_status(item, reference_date) for item in group)
        serious_delayed_count = status_counter["seriously_delayed"]
        delayed_count_value = status_counter["delayed"]
        not_started_count = status_counter["not_started_by_plan"]
        status, status_label = _floor_status(
            serious_delayed_count=serious_delayed_count,
            delayed_count=delayed_count_value,
            not_started_count=not_started_count,
            task_count=len(group),
            deviation=deviation,
        )
        rows.append(
            DashboardUnifiedMatrixRow(
                building=first if dimensions[0] == "building" else None,
                discipline=first if dimensions[0] == "discipline" else None,
                floor=second if dimensions[1] == "floor" else None,
                task_count=len(group),
                actual_percent=actual,
                planned_percent=planned,
                progress_deviation=deviation,
                delayed_count=delayed_count(group, reference_date),
                serious_delayed_count=serious_delayed_count,
                not_started_count=not_started_count,
                status=status,
                status_label=status_label,
                calculation_method=algorithm,
            )
        )
    rows.sort(key=lambda row: (sort_dimension_value(dimensions[0], row.building or row.discipline), sort_dimension_value(dimensions[1], row.floor)))
    return rows


def _building_elevation_rows(
    db: Session,
    project_id: int,
    items: list[ProgressItem],
    profile,
    algorithm: str,
    reference_date: date,
) -> list[DashboardBuildingElevation]:
    groups: dict[str, dict[str, list[ProgressItem]]] = defaultdict(lambda: defaultdict(list))
    for item in items:
        groups[_dimension_value(item, "building")][_dimension_value(item, "floor")].append(item)

    rows: list[DashboardBuildingElevation] = []
    for building, floor_groups in groups.items():
        building_items = [item for group in floor_groups.values() for item in group]
        building_actual, _, _ = aggregate_progress(building_items, profile, "actual_percent", algorithm)
        building_planned, _, _ = aggregate_progress(building_items, profile, "planned_percent", algorithm)
        building_deviation = (
            round(building_actual - building_planned, 4)
            if building_actual is not None and building_planned is not None
            else None
        )
        floors = [
            _building_elevation_floor(db, project_id, floor, group, profile, algorithm, reference_date)
            for floor, group in floor_groups.items()
        ]
        floors.sort(key=lambda row: sort_dimension_value("floor", row.floor), reverse=True)
        status, status_label = _floor_status(
            serious_delayed_count=sum(floor.serious_delayed_count for floor in floors),
            delayed_count=sum(floor.delayed_count for floor in floors),
            not_started_count=sum(floor.not_started_count for floor in floors),
            task_count=sum(floor.task_count for floor in floors),
            deviation=building_deviation,
        )
        rows.append(
            DashboardBuildingElevation(
                building=building,
                floors=floors,
                task_count=len(building_items),
                actual_percent=building_actual,
                planned_percent=building_planned,
                progress_deviation=building_deviation,
                status=status,
                status_label=status_label,
                message=None if floors else "当前楼栋暂无楼层数据。",
            )
        )
    rows.sort(key=lambda row: sort_dimension_value("building", row.building))
    return rows


def _building_elevation_floor(
    db: Session,
    project_id: int,
    floor: str,
    group: list[ProgressItem],
    profile,
    algorithm: str,
    reference_date: date,
) -> DashboardBuildingElevationFloor:
    actual, _, _ = aggregate_progress(group, profile, "actual_percent", algorithm)
    planned, _, _ = aggregate_progress(group, profile, "planned_percent", algorithm)
    deviation = round(actual - planned, 4) if actual is not None and planned is not None else None
    status_counts = Counter(_delay_status(item, reference_date) for item in group)
    serious_delayed_count = status_counts["seriously_delayed"]
    delayed_count_value = status_counts["delayed"]
    not_started_count = status_counts["not_started_by_plan"]
    status, status_label = _floor_status(
        serious_delayed_count=serious_delayed_count,
        delayed_count=delayed_count_value,
        not_started_count=not_started_count,
        task_count=len(group),
        deviation=deviation,
    )
    major_delayed = [
        item
        for item in delayed_items(group, reference_date)
        if _delay_status(item, reference_date) in {"seriously_delayed", "delayed"}
    ]
    return DashboardBuildingElevationFloor(
        floor=floor,
        task_count=len(group),
        actual_percent=actual,
        planned_percent=planned,
        progress_deviation=deviation,
        deviation=deviation,
        delayed_count=delayed_count_value,
        serious_delayed_count=serious_delayed_count,
        not_started_count=not_started_count,
        status=status,
        status_label=status_label,
        major_delayed_tasks=_delayed_item_rows_for_items(db, project_id, major_delayed[:8], reference_date),
        calculation_method=algorithm,
    )


def _floor_status(
    *,
    serious_delayed_count: int,
    delayed_count: int,
    not_started_count: int,
    task_count: int,
    deviation: float | None,
    thresholds: DelayThresholds = DEFAULT_DELAY_THRESHOLDS,
) -> tuple[str, str]:
    if task_count <= 0:
        return "no_data", "无数据"
    if not_started_count == task_count:
        return "not_started_by_plan", "未到计划开始"
    if deviation is None:
        return "no_data", "无数据"
    status = classify_delay_status(deviation, thresholds)
    return status, DELAY_STATUS_LABELS.get(status, "未知")


def _delayed_item_rows(db: Session, project_id: int, items: list[ProgressItem], reference_date: date) -> list[AnalyticsDelayedItem]:
    delayed = delayed_items(items, reference_date)
    return _delayed_item_rows_for_items(db, project_id, delayed[:50], reference_date)


def _delayed_item_rows_for_items(db: Session, project_id: int, items: list[ProgressItem], reference_date: date) -> list[AnalyticsDelayedItem]:
    item_ids = [item.id for item in items if item.id is not None]
    rectification_rows = db.execute(
        select(RectificationItem.progress_item_id, RectificationItem.id).where(
            RectificationItem.project_id == project_id,
            RectificationItem.progress_item_id.in_(item_ids),
            RectificationItem.source_type == "progress_item",
        )
    ).all() if item_ids else []
    rectification_by_item = {progress_item_id: rectification_id for progress_item_id, rectification_id in rectification_rows}
    return [
        AnalyticsDelayedItem(
            id=item.id,
            progress_item_id=item.id,
            task_id=item.task_id,
            task_name=display_text(item.task_name, "未填写施工项"),
            wbs_code=item.wbs_code,
            task_code=item.task_code,
            area=item.area,
            construction_unit=_construction_unit(item),
            building=display_text(item.building, "未填写楼栋"),
            floor=display_text(item.floor, "未填写楼层"),
            discipline=display_text(item.discipline, "未填写专业"),
            system_name=display_text(item.system_name, "未填写系统"),
            unit=item.unit,
            actual_percent=item.actual_percent,
            planned_percent=item.planned_percent,
            time_planned_percent=item.time_planned_percent,
            imported_planned_percent=item.imported_planned_percent,
            progress_deviation=calculated_deviation(item, reference_date),
            status=item.status,
            delay_level=delay_level_for_deviation(calculated_deviation(item, reference_date))[0],
            delay_level_label=delay_level_for_deviation(calculated_deviation(item, reference_date))[1],
            delay_message=build_delay_message(item),
            rectification_item_id=rectification_by_item.get(item.id),
            has_rectification=item.id in rectification_by_item,
        )
        for item in items
    ]


def _apply_filters(items: list[ProgressItem], reference_date: date, **filters: str | None) -> list[ProgressItem]:
    filtered = items
    comparisons = {
        "construction_unit": lambda item: _construction_unit(item) or "未填写施工单位",
        "building": lambda item: display_text(item.building, "未填写楼栋"),
        "floor": lambda item: display_text(item.floor, "未填写楼层"),
        "discipline": lambda item: display_text(item.discipline, "未填写专业"),
        "system_name": lambda item: display_text(item.system_name, "未填写系统"),
    }
    for field, getter in comparisons.items():
        value = _clean(filters.get(field))
        if value:
            filtered = [item for item in filtered if getter(item) == value]
    status = _clean(filters.get("status"))
    if status:
        filtered = [
            item
            for item in filtered
            if item.status == status or _status_matches(_delay_status(item, reference_date), status)
        ]
    return filtered


def _options(items: list[ProgressItem]) -> DashboardUnifiedOptions:
    return DashboardUnifiedOptions(
        construction_units=_sorted_unique((_construction_unit(item) for item in items), "construction_unit"),
        buildings=_sorted_unique((display_text(item.building, "未填写楼栋") for item in items), "building"),
        floors=_sorted_unique((display_text(item.floor, "未填写楼层") for item in items), "floor"),
        disciplines=_sorted_unique((display_text(item.discipline, "未填写专业") for item in items), "discipline"),
        systems=_sorted_unique((display_text(item.system_name, "未填写系统") for item in items), "system_name"),
        statuses=_sorted_unique((item.status for item in items if item.status), "status"),
    )


def _warning_counts_by_item(db: Session, project_id: int, batch_ids: list[int], items: list[ProgressItem]) -> Counter[int]:
    task_to_item = {item.task_id: item.id for item in items if item.task_id is not None and item.id is not None}
    if not task_to_item:
        return Counter()
    rows = db.execute(
        select(WarningRecord.task_id).where(
            WarningRecord.project_id == project_id,
            WarningRecord.batch_id.in_(batch_ids),
            WarningRecord.task_id.in_(list(task_to_item)),
        )
    ).all()
    return Counter(task_to_item[task_id] for (task_id,) in rows if task_id in task_to_item)


def _rectification_counts_by_item(db: Session, project_id: int, batch_ids: list[int], items: list[ProgressItem]) -> Counter[int]:
    item_ids = [item.id for item in items if item.id is not None]
    if not item_ids:
        return Counter()
    rows = db.execute(
        select(RectificationItem.progress_item_id).where(
            RectificationItem.project_id == project_id,
            RectificationItem.batch_id.in_(batch_ids),
            RectificationItem.progress_item_id.in_(item_ids),
        )
    ).all()
    return Counter(progress_item_id for (progress_item_id,) in rows if progress_item_id is not None)


def _warning_summary(db: Session, project_id: int, batch_ids: list[int], items: list[ProgressItem], algorithm: str) -> DashboardUnifiedSummary:
    task_ids = [item.task_id for item in items if item.task_id is not None]
    rows = []
    if task_ids:
        rows = list(
            db.scalars(
                select(WarningRecord).where(
                    WarningRecord.project_id == project_id,
                    WarningRecord.batch_id.in_(batch_ids),
                    WarningRecord.task_id.in_(task_ids),
                )
            )
        )
    levels = Counter(row.level or "warning" for row in rows)
    return DashboardUnifiedSummary(
        total=len(rows),
        unresolved=sum(1 for row in rows if not row.is_resolved),
        critical=levels["critical"],
        warning=levels["warning"],
        info=levels["info"],
        calculation_method=algorithm,
    )


def _rectification_summary(db: Session, project_id: int, batch_ids: list[int], items: list[ProgressItem], algorithm: str) -> DashboardUnifiedSummary:
    item_ids = [item.id for item in items if item.id is not None]
    rows = []
    if item_ids:
        rows = list(
            db.scalars(
                select(RectificationItem).where(
                    RectificationItem.project_id == project_id,
                    RectificationItem.batch_id.in_(batch_ids),
                    RectificationItem.progress_item_id.in_(item_ids),
                )
            )
        )
    statuses = Counter(row.status for row in rows)
    today = date.today()
    return DashboardUnifiedSummary(
        total=len(rows),
        open=statuses["open"],
        in_progress=statuses["in_progress"],
        completed=statuses["completed"],
        closed=statuses["closed"],
        overdue=sum(1 for row in rows if row.status != "closed" and row.planned_finish_date and row.planned_finish_date < today),
        critical=sum(1 for row in rows if row.delay_level in {"seriously_delayed", "seriously_delay", "critical"}),
        calculation_method=algorithm,
    )


def _delay_distribution(items: list[ProgressItem], reference_date: date, algorithm: str) -> list[DashboardUnifiedDelayDistributionRow]:
    counter = Counter(_delay_status(item, reference_date) for item in items)
    return [
        DashboardUnifiedDelayDistributionRow(status=status, status_label=DELAY_STATUS_LABELS[status], count=counter[status], calculation_method=algorithm)
        for status in DELAY_STATUS_ORDER
        if counter[status] > 0
    ]


def _group_by_dimension(items: Iterable[ProgressItem], dimension: str) -> dict[str, list[ProgressItem]]:
    groups: dict[str, list[ProgressItem]] = defaultdict(list)
    for item in items:
        groups[_dimension_value(item, dimension)].append(item)
    return groups


def _dimension_value(item: ProgressItem, dimension: str) -> str:
    if dimension == "construction_unit":
        return _construction_unit(item) or "未填写施工单位"
    fallback = {
        "building": "未填写楼栋",
        "floor": "未填写楼层",
        "discipline": "未填写专业",
        "system_name": "未填写系统",
    }.get(dimension, "未填写")
    return display_text(getattr(item, dimension, None), fallback)


def _construction_unit(item: ProgressItem) -> str | None:
    value = getattr(item, "construction_unit", None)
    if value:
        return str(value).strip()
    if not item.extra_fields:
        return None
    try:
        extra = json.loads(item.extra_fields)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(extra, dict):
        return None
    for alias in CONSTRUCTION_UNIT_ALIASES:
        value = extra.get(alias)
        if value:
            return str(value).strip()
    return None


def _delay_status(
    item: ProgressItem,
    reference_date: date,
    thresholds: DelayThresholds = DEFAULT_DELAY_THRESHOLDS,
) -> str:
    if item.status in {"not_started_by_plan", "missing_plan_dates", "invalid_plan_dates"}:
        return item.status
    deviation = calculated_deviation(item, reference_date)
    if deviation is None:
        return item.status if item.status in {"completed", "normal", "ahead"} else "unknown"
    return classify_delay_status(deviation, thresholds)


def _status_matches(actual: str | None, requested: str) -> bool:
    if actual == requested:
        return True
    if requested == "delayed_or_worse":
        return actual in {"seriously_delayed", "delayed"}
    if requested == "any_delayed":
        return actual in {"seriously_delayed", "delayed", "slightly_delayed"}
    return False


def _sorted_unique(values: Iterable[str | None], dimension: str) -> list[str]:
    rows = sorted({value for value in values if value}, key=lambda value: sort_dimension_value(dimension, value))
    return rows


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _single_data_date(batches: list[ImportBatch]) -> bool:
    return len({batch.data_date for batch in batches}) == 1


def _scope_label(batches: list[ImportBatch], is_single_batch: bool, data_date: date | None, import_group_id: str | None, sheet_name: str | None) -> str:
    if not batches:
        return "空数据范围"
    if is_single_batch:
        return f"单批次 / Sheet：{batches[0].sheet_name or batches[0].id}"
    if sheet_name:
        return f"Sheet：{sheet_name}"
    if import_group_id:
        return f"导入批次组：{import_group_id}"
    selected_date = data_date or batches[0].data_date
    date_text = selected_date.isoformat() if selected_date else "未填写数据日期"
    return f"项目总览：{date_text} 已发布 Sheet 聚合"
