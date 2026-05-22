from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.import_batch import ImportBatch
from app.models.import_validation_issue import ImportValidationIssue
from app.models.project import Project
from app.models.rectification_item import RectificationItem
from app.schemas.analytics import (
    AnalyticsBuildingFloorItem,
    AnalyticsBuildingFloorResponse,
    AnalyticsDataQualityResponse,
    AnalyticsDelayedItem,
    AnalyticsDelayedRankingResponse,
    AnalyticsFieldsResponse,
    AnalyticsGroupByResponse,
    AnalyticsGroupRow,
    AnalyticsInsightResponse,
    AnalyticsOverviewResponse,
    AnalyticsPlanVsActualResponse,
    AnalyticsPlanVsActualRow,
    DashboardUnifiedResponse,
    ProjectOverviewBatch,
    ProjectOverviewResponse,
    AnalyticsTrendPoint,
    AnalyticsTrendResponse,
    BaselineComparisonResponse,
    DeviationAttributionResponse,
    DeviationAttributionRow,
)
from app.services.dashboard_unified_service import build_dashboard_unified
from app.services.progress_insight_service import generate_progress_insight
from app.services.analytics_service import (
    AGGREGATIONS,
    DIMENSIONS,
    METRICS,
    aggregate_metric,
    aggregate_progress,
    apply_time_based_progress,
    available_calculation_methods,
    baseline_context,
    baseline_name,
    build_delay_message,
    calculated_deviation,
    delayed_count,
    delayed_items,
    delay_reference_date,
    delay_level_for_deviation,
    display_text,
    effective_baseline_plan,
    effective_calculation_method,
    filter_items_by_baseline,
    get_published_batch,
    group_items,
    group_items_multi,
    item_units,
    list_items,
    list_published_batches,
    quantity_sum,
    resolve_baseline_plan,
    resolve_calculation_profile,
    sort_dimension_value,
    statistics_context,
    status_counts,
    validate_aggregation,
    validate_dimension,
    validate_metric,
)
from app.schemas.validation import ValidationIssueCodeCount

router = APIRouter(prefix="/projects/{project_id}/analytics", tags=["analytics"])


def get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PROJECT_NOT_FOUND", "message": "当前项目不存在或已被清理。"},
        )
    return project


def get_batch_items_or_404(project_id: int, batch_id: int | None, db: Session):
    batch = get_published_batch(db, project_id, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Published import batch not found")
    return batch, apply_time_based_progress(list_items(db, project_id, batch.id), batch)


@router.get("/fields", response_model=AnalyticsFieldsResponse)
def get_analytics_fields(project_id: int, batch_id: int | None = None, db: Session = Depends(get_db)) -> AnalyticsFieldsResponse:
    project = get_project_or_404(project_id, db)
    if batch_id is not None:
        get_batch_items_or_404(project_id, batch_id, db)
    return AnalyticsFieldsResponse(dimensions=DIMENSIONS, metrics=METRICS, aggregations=AGGREGATIONS)


@router.get("/dashboard-unified", response_model=DashboardUnifiedResponse)
def dashboard_unified(
    project_id: int,
    data_date: str | None = None,
    import_group_id: str | None = None,
    batch_id: int | None = None,
    sheet_name: str | None = None,
    construction_unit: str | None = None,
    building: str | None = None,
    floor: str | None = None,
    discipline: str | None = None,
    system_name: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    calculation_profile_id: int | None = None,
    calculation_method: str | None = None,
    baseline_plan_id: int | None = None,
    db: Session = Depends(get_db),
) -> DashboardUnifiedResponse:
    project = get_project_or_404(project_id, db)
    parsed_data_date = None
    if data_date:
        try:
            from datetime import date

            parsed_data_date = date.fromisoformat(data_date)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid data_date") from exc
    return build_dashboard_unified(
        db,
        project,
        data_date=parsed_data_date,
        import_group_id=import_group_id,
        batch_id=batch_id,
        sheet_name=sheet_name,
        construction_unit=construction_unit,
        building=building,
        floor=floor,
        discipline=discipline,
        system_name=system_name,
        status=status_filter,
        calculation_profile_id=calculation_profile_id,
        calculation_method=calculation_method,
        baseline_plan_id=baseline_plan_id,
    )


@router.get("/overview", response_model=AnalyticsOverviewResponse)
def get_overview(
    project_id: int,
    batch_id: int | None = None,
    calculation_profile_id: int | None = None,
    calculation_method: str | None = None,
    baseline_plan_id: int | None = None,
    db: Session = Depends(get_db),
) -> AnalyticsOverviewResponse:
    project = get_project_or_404(project_id, db)
    batch, items = get_batch_items_or_404(project_id, batch_id, db)
    profile = resolve_calculation_profile(db, project_id, calculation_profile_id or batch.calculation_profile_id)
    calculation_method = effective_calculation_method(project, calculation_method)
    baseline = effective_baseline_plan(db, project_id, batch, baseline_plan_id)
    items = filter_items_by_baseline(items, baseline)
    actual_percent, unit_mixed, warning = aggregate_progress(items, profile, "actual_percent", calculation_method)
    planned_percent, planned_unit_mixed, planned_warning = aggregate_progress(items, profile, "planned_percent", calculation_method)
    stats_meta = statistics_context(items, profile, calculation_method)
    methods = available_calculation_methods(items)
    units = item_units(items)
    time_planned_percent, _, _ = aggregate_progress(items, profile, "time_planned_percent")
    imported_planned_percent, _, _ = aggregate_progress(items, profile, "imported_planned_percent")
    total_quantity, total_unit_mixed, total_warning = quantity_sum(items, "total_quantity", profile)
    actual_quantity, actual_unit_mixed, actual_warning = quantity_sum(items, "actual_quantity", profile)
    remaining_quantity, remaining_unit_mixed, remaining_warning = quantity_sum(items, "remaining_quantity", profile)

    warnings = [{"code": "unit_mixed", "message": message} for message in {warning, planned_warning, total_warning, actual_warning, remaining_warning} if message]
    baseline_meta = baseline_context(db, project_id, batch, baseline_plan_id)
    if items and actual_percent is None:
        warnings.append(
            {
                "code": "no_calculable_progress",
                "message": "当前批次缺少可计算的实际进度字段。请检查字段映射是否包含实际完成率、累计完成量或实际完成量。",
            }
        )
        warnings.append(
            {
                "code": "no_calculable_actual_progress",
                "message": "当前批次缺少可计算的实际进度字段。请检查字段映射是否包含实际完成率、累计完成量或实际完成量。",
            }
        )
    if items and planned_percent is None:
        warnings.append(
            {
                "code": "no_calculable_planned_progress",
                "message": "当前批次缺少计划进度字段，无法计算进度偏差和滞后项。",
            }
        )
    if batch.data_quality_score is not None and batch.data_quality_score < 60:
        warnings.append(
            {
                "code": "low_data_quality",
                "message": "当前批次数据质量较低，建议检查字段映射、表头行和异常数据。",
            }
        )
    if stats_meta.weight_warning:
        warnings.append({"code": "weight_quality", "message": stats_meta.weight_warning})
    if stats_meta.algorithm == "avg_percent" and not stats_meta.weight_count:
        warnings.append(
            {
                "code": "no_valid_weight",
                "message": "当前数据未识别到有效权重，系统使用任务平均完成率。",
            }
        )
    deviation = round(actual_percent - planned_percent, 4) if actual_percent is not None and planned_percent is not None else None
    return AnalyticsOverviewResponse(
        batch_id=batch.id,
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
        included_batch_count=1,
        included_batches=[
            ProjectOverviewBatch(
                batch_id=batch.id,
                sheet_name=batch.sheet_name,
                import_group_id=batch.import_group_id,
                import_group_name=batch.import_group_name,
                data_date=batch.data_date,
                actual_percent=actual_percent,
                planned_percent=planned_percent,
                item_count=len(items),
            )
        ],
        baseline_plan_id=baseline.id if baseline else None,
        baseline_plan_name=baseline.name if baseline else None,
        **baseline_meta,
        item_count=len(items),
        task_count=len({item.task_id for item in items if item.task_id is not None}),
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
        warning=warnings[0]["message"] if warnings else None,
        warnings=warnings,
        batch_status_label="已冻结" if batch.is_frozen else "正常",
        batch_is_frozen=batch.is_frozen,
        project_is_archived=project.is_archived,
    )


@router.get("/project-overview", response_model=ProjectOverviewResponse)
def get_project_overview(
    project_id: int,
    calculation_profile_id: int | None = None,
    calculation_method: str | None = None,
    db: Session = Depends(get_db),
) -> ProjectOverviewResponse:
    project = get_project_or_404(project_id, db)
    latest_batch = get_published_batch(db, project_id, None)
    if latest_batch is None:
        return ProjectOverviewResponse(
            calculation_method=effective_calculation_method(project, calculation_method) or "auto",
            empty=True,
            message="当前项目暂无已发布批次，工作台暂无项目总进度。",
            scope_label="暂无已发布批次",
        )

    date_statement = select(ImportBatch).where(
        ImportBatch.project_id == project_id,
        ImportBatch.is_active.is_(True),
        ImportBatch.status == "published",
    )
    if latest_batch.data_date is None:
        date_statement = date_statement.where(ImportBatch.data_date.is_(None))
    else:
        date_statement = date_statement.where(ImportBatch.data_date == latest_batch.data_date)

    date_batches = list(
        db.execute(
            date_statement.order_by(
                ImportBatch.created_at.asc(),
                ImportBatch.id.asc(),
            )
        ).scalars()
    )
    if latest_batch.import_group_id:
        grouped_batches = [batch for batch in date_batches if batch.import_group_id == latest_batch.import_group_id]
        batches = grouped_batches or date_batches
    else:
        batches = date_batches

    batch_items: list[tuple[ImportBatch, list]] = []
    all_items = []
    for batch in batches:
        items = apply_time_based_progress(list_items(db, project_id, batch.id), batch)
        batch_items.append((batch, items))
        all_items.extend(items)

    profile = resolve_calculation_profile(db, project_id, calculation_profile_id or latest_batch.calculation_profile_id)
    calculation_method = effective_calculation_method(project, calculation_method)
    actual_percent, actual_unit_mixed, actual_warning = aggregate_progress(all_items, profile, "actual_percent", calculation_method)
    planned_percent, planned_unit_mixed, planned_warning = aggregate_progress(all_items, profile, "time_planned_percent", calculation_method)
    stats_meta = statistics_context(all_items, profile, calculation_method)
    methods = available_calculation_methods(all_items)
    units = item_units(all_items)
    deviation = round(actual_percent - planned_percent, 4) if actual_percent is not None and planned_percent is not None else None
    warnings = [{"code": "unit_mixed", "message": message} for message in {actual_warning, planned_warning} if message]
    if stats_meta.weight_warning:
        warnings.append({"code": "weight_quality", "message": stats_meta.weight_warning})

    included_batches = []
    for batch, items in batch_items:
        batch_actual, _, _ = aggregate_progress(items, profile, "actual_percent", calculation_method)
        batch_planned, _, _ = aggregate_progress(items, profile, "time_planned_percent", calculation_method)
        included_batches.append(
            ProjectOverviewBatch(
                batch_id=batch.id,
                sheet_name=batch.sheet_name,
                import_group_id=batch.import_group_id,
                import_group_name=batch.import_group_name,
                data_date=batch.data_date,
                actual_percent=batch_actual,
                planned_percent=batch_planned,
                item_count=len(items),
            )
        )

    if len(batches) == 1:
        scope_label = "当前仅检测到 1 个已发布批次，工作台显示该批次进度。"
    else:
        scope_label = f"最新数据日期 {latest_batch.data_date.isoformat() if latest_batch.data_date else '-'}，已聚合 {len(batches)} 个 Sheet"

    return ProjectOverviewResponse(
        project_actual_percent=actual_percent,
        project_planned_percent=planned_percent,
        project_deviation=deviation,
        actual_progress=actual_percent,
        planned_progress=planned_percent,
        progress_deviation=deviation,
        data_date=latest_batch.data_date,
        included_batch_count=len(batches),
        included_batches=included_batches,
        calculation_method=stats_meta.algorithm,
        calculation_method_name=stats_meta.label,
        recommended_method=next((str(method["code"]) for method in methods if method.get("recommended")), None),
        recommendation_reason=stats_meta.reason,
        available_methods=methods,
        mixed_units=len(units) > 1,
        unit_list=units,
        statistics_label=stats_meta.label,
        weight_sum=stats_meta.weight_total,
        item_count=len(all_items),
        task_count=len({item.task_id for item in all_items if item.task_id is not None}),
        is_project_aggregate=True,
        empty=False,
        message=None,
        scope_label=scope_label,
        warning=warnings[0]["message"] if warnings else None,
        warnings=warnings,
    )


@router.get("/group-by", response_model=AnalyticsGroupByResponse)
def group_by(
    project_id: int,
    batch_id: int | None = None,
    dimension: str = Query("discipline"),
    metric: str = Query("actual_percent"),
    aggregation: str = Query("avg"),
    calculation_profile_id: int | None = None,
    calculation_method: str | None = None,
    baseline_plan_id: int | None = None,
    db: Session = Depends(get_db),
) -> AnalyticsGroupByResponse:
    project = get_project_or_404(project_id, db)
    try:
        validate_dimension(dimension)
        validate_metric(metric)
        validate_aggregation(aggregation)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    batch, items = get_batch_items_or_404(project_id, batch_id, db)
    profile = resolve_calculation_profile(db, project_id, calculation_profile_id or batch.calculation_profile_id)
    calculation_method = effective_calculation_method(project, calculation_method)
    baseline = effective_baseline_plan(db, project_id, batch, baseline_plan_id)
    items = filter_items_by_baseline(items, baseline)
    algorithm = calculation_method or (profile.group_algorithm if profile else "auto") or "auto"
    rows = []
    for dimension_value, group in group_items(items, dimension).items():
        value, unit_mixed, warning = aggregate_metric(group, metric, aggregation, profile, algorithm)
        rows.append(
            AnalyticsGroupRow(
                dimension_value=dimension_value,
                value=value,
                count=len(group),
                units=item_units(group),
                unit_mixed=unit_mixed,
                warning=warning,
            )
        )
    rows.sort(key=lambda row: sort_dimension_value(dimension, row.dimension_value))
    return AnalyticsGroupByResponse(batch_id=batch.id, dimension=dimension, metric=metric, aggregation=aggregation, rows=rows)


@router.get("/plan-vs-actual", response_model=AnalyticsPlanVsActualResponse)
def plan_vs_actual(
    project_id: int,
    batch_id: int | None = None,
    dimension: str = Query("discipline"),
    calculation_profile_id: int | None = None,
    calculation_method: str | None = None,
    baseline_plan_id: int | None = None,
    db: Session = Depends(get_db),
) -> AnalyticsPlanVsActualResponse:
    project = get_project_or_404(project_id, db)
    try:
        validate_dimension(dimension)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    batch, items = get_batch_items_or_404(project_id, batch_id, db)
    profile = resolve_calculation_profile(db, project_id, calculation_profile_id or batch.calculation_profile_id)
    calculation_method = effective_calculation_method(project, calculation_method)
    baseline = effective_baseline_plan(db, project_id, batch, baseline_plan_id)
    items = filter_items_by_baseline(items, baseline)
    algorithm = calculation_method or (profile.group_algorithm if profile else "auto") or "auto"
    rows = []
    for dimension_value, group in group_items(items, dimension).items():
        actual_percent, actual_unit_mixed, actual_warning = aggregate_progress(group, profile, "actual_percent", algorithm)
        planned_percent, planned_unit_mixed, planned_warning = aggregate_progress(group, profile, "planned_percent", algorithm)
        time_planned_percent, _, _ = aggregate_progress(group, profile, "time_planned_percent", algorithm)
        imported_planned_percent, _, _ = aggregate_progress(group, profile, "imported_planned_percent", algorithm)
        deviation = round(actual_percent - planned_percent, 4) if actual_percent is not None and planned_percent is not None else None
        warning = actual_warning or planned_warning
        rows.append(
            AnalyticsPlanVsActualRow(
                dimension_value=dimension_value,
                actual_percent=actual_percent,
                planned_percent=planned_percent,
                time_planned_percent=time_planned_percent,
                imported_planned_percent=imported_planned_percent,
                progress_deviation=deviation,
                delayed_count=delayed_count(group, delay_reference_date(batch)),
                count=len(group),
                units=item_units(group),
                unit_mixed=actual_unit_mixed or planned_unit_mixed,
                warning=warning,
            )
        )
    rows.sort(key=lambda row: sort_dimension_value(dimension, row.dimension_value))
    return AnalyticsPlanVsActualResponse(batch_id=batch.id, dimension=dimension, rows=rows)


DEFAULT_ATTRIBUTION_DIMENSIONS = ["construction_unit", "discipline", "floor"]


@router.get("/deviation-attribution", response_model=DeviationAttributionResponse)
def deviation_attribution(
    project_id: int,
    batch_id: int | None = None,
    dimensions: str = Query(",".join(DEFAULT_ATTRIBUTION_DIMENSIONS), description="逗号分隔的 1~3 个维度,默认 construction_unit,discipline,floor"),
    calculation_profile_id: int | None = None,
    calculation_method: str | None = None,
    baseline_plan_id: int | None = None,
    top_n: int | None = Query(None, ge=1, le=200, description="按 |progress_deviation| 降序截取的行数"),
    db: Session = Depends(get_db),
) -> DeviationAttributionResponse:
    project = get_project_or_404(project_id, db)
    dimension_list = [token.strip() for token in dimensions.split(",") if token.strip()]
    if not dimension_list:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="至少需要 1 个维度")
    if len(dimension_list) > 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="最多支持 3 个维度组合")
    try:
        for dimension in dimension_list:
            validate_dimension(dimension)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    batch, items = get_batch_items_or_404(project_id, batch_id, db)
    profile = resolve_calculation_profile(db, project_id, calculation_profile_id or batch.calculation_profile_id)
    calculation_method = effective_calculation_method(project, calculation_method)
    baseline = effective_baseline_plan(db, project_id, batch, baseline_plan_id)
    items = filter_items_by_baseline(items, baseline)
    algorithm = calculation_method or (profile.group_algorithm if profile else "auto") or "auto"

    overall_actual, _, _ = aggregate_progress(items, profile, "actual_percent", algorithm)
    overall_planned, _, _ = aggregate_progress(items, profile, "planned_percent", algorithm)
    overall_deviation = (
        round(overall_actual - overall_planned, 4)
        if overall_actual is not None and overall_planned is not None
        else None
    )

    rows: list[DeviationAttributionRow] = []
    grouped = group_items_multi(items, dimension_list)
    for key, group in grouped.items():
        actual_percent, _, actual_warning = aggregate_progress(group, profile, "actual_percent", algorithm)
        planned_percent, _, planned_warning = aggregate_progress(group, profile, "planned_percent", algorithm)
        deviation = (
            round(actual_percent - planned_percent, 4)
            if actual_percent is not None and planned_percent is not None
            else None
        )
        abs_dev = abs(deviation) if deviation is not None else None
        contribution = (
            round(deviation * (len(group) / len(items)), 4)
            if deviation is not None and items
            else None
        )
        rows.append(
            DeviationAttributionRow(
                dimension_values={dim: value for dim, value in zip(dimension_list, key)},
                actual_percent=actual_percent,
                planned_percent=planned_percent,
                progress_deviation=deviation,
                abs_deviation=abs_dev,
                delayed_count=delayed_count(group, delay_reference_date(batch)),
                count=len(group),
                contribution=contribution,
                warning=actual_warning or planned_warning,
            )
        )

    rows.sort(key=lambda row: (-(row.abs_deviation or 0.0), -row.count))
    if top_n is not None:
        rows = rows[:top_n]

    return DeviationAttributionResponse(
        batch_id=batch.id,
        dimensions=dimension_list,
        total_count=len(items),
        overall_actual_percent=overall_actual,
        overall_planned_percent=overall_planned,
        overall_progress_deviation=overall_deviation,
        rows=rows,
    )


@router.get("/building-floor", response_model=AnalyticsBuildingFloorResponse)
def building_floor(
    project_id: int,
    batch_id: int | None = None,
    building: str | None = None,
    calculation_profile_id: int | None = None,
    calculation_method: str | None = None,
    baseline_plan_id: int | None = None,
    db: Session = Depends(get_db),
) -> AnalyticsBuildingFloorResponse:
    project = get_project_or_404(project_id, db)
    batch, items = get_batch_items_or_404(project_id, batch_id, db)
    profile = resolve_calculation_profile(db, project_id, calculation_profile_id or batch.calculation_profile_id)
    calculation_method = effective_calculation_method(project, calculation_method)
    baseline = effective_baseline_plan(db, project_id, batch, baseline_plan_id)
    items = filter_items_by_baseline(items, baseline)
    algorithm = calculation_method or (profile.group_algorithm if profile else "auto") or "auto"

    def building_value(item) -> str:
        return item.building or "未填写楼栋"

    def floor_value(item) -> str:
        return item.floor or "未填写楼层"

    buildings = sorted({building_value(item) for item in items}, key=lambda value: sort_dimension_value("building", value))
    selected_building = building or None
    filtered_items = [item for item in items if building_value(item) == building] if building else items

    groups = {}
    for item in filtered_items:
        groups.setdefault((building_value(item), floor_value(item)), []).append(item)

    rows = []
    for (building_name, floor_name), group in groups.items():
        actual_percent, actual_unit_mixed, actual_warning = aggregate_progress(group, profile, "actual_percent", algorithm)
        planned_percent, planned_unit_mixed, planned_warning = aggregate_progress(group, profile, "planned_percent", algorithm)
        time_planned_percent, _, _ = aggregate_progress(group, profile, "time_planned_percent", algorithm)
        imported_planned_percent, _, _ = aggregate_progress(group, profile, "imported_planned_percent", algorithm)
        deviation = round(actual_percent - planned_percent, 4) if actual_percent is not None and planned_percent is not None else None
        rows.append(
            AnalyticsBuildingFloorItem(
                building=building_name,
                floor=floor_name,
                task_count=len(group),
                actual_percent=actual_percent,
                planned_percent=planned_percent,
                time_planned_percent=time_planned_percent,
                imported_planned_percent=imported_planned_percent,
                progress_deviation=deviation,
                delayed_count=delayed_count(group, delay_reference_date(batch)),
                unit_mixed=actual_unit_mixed or planned_unit_mixed,
                units=item_units(group),
                warning=actual_warning or planned_warning,
            )
        )

    rows.sort(key=lambda row: (sort_dimension_value("building", row.building), sort_dimension_value("floor", row.floor)))
    return AnalyticsBuildingFloorResponse(batch_id=batch.id, buildings=buildings, selected_building=selected_building, items=rows)


@router.get("/delayed-ranking", response_model=AnalyticsDelayedRankingResponse)
def delayed_ranking(
    project_id: int,
    batch_id: int | None = None,
    limit: int = Query(20, ge=1, le=100),
    baseline_plan_id: int | None = None,
    db: Session = Depends(get_db),
) -> AnalyticsDelayedRankingResponse:
    get_project_or_404(project_id, db)
    batch, items = get_batch_items_or_404(project_id, batch_id, db)
    baseline = effective_baseline_plan(db, project_id, batch, baseline_plan_id)
    items = filter_items_by_baseline(items, baseline)
    delayed = delayed_items(items, delay_reference_date(batch))
    rectification_rows = db.execute(
        select(RectificationItem.progress_item_id, RectificationItem.id).where(
            RectificationItem.project_id == project_id,
            RectificationItem.progress_item_id.in_([item.id for item in delayed if item.id is not None]),
            RectificationItem.source_type == "progress_item",
        )
    ).all()
    rectification_by_progress_item = {progress_item_id: rectification_id for progress_item_id, rectification_id in rectification_rows}
    rows = [
        AnalyticsDelayedItem(
            id=item.id,
            progress_item_id=item.id,
            task_id=item.task_id,
            task_name=display_text(item.task_name, "未填写施工项"),
            wbs_code=item.wbs_code,
            task_code=item.task_code,
            area=item.area,
            construction_unit=getattr(item, "construction_unit", None),
            building=display_text(item.building, "未填写楼栋"),
            floor=display_text(item.floor, "未填写楼层"),
            discipline=display_text(item.discipline, "未填写专业"),
            system_name=display_text(item.system_name, "未填写系统"),
            unit=item.unit,
            actual_percent=item.actual_percent,
            planned_percent=item.planned_percent,
            time_planned_percent=item.time_planned_percent,
            imported_planned_percent=item.imported_planned_percent,
            progress_deviation=calculated_deviation(item, delay_reference_date(batch)),
            status=item.status,
            schedule_phase=item.schedule_phase,
            delay_level=delay_level_for_deviation(calculated_deviation(item, delay_reference_date(batch)))[0],
            delay_level_label=delay_level_for_deviation(calculated_deviation(item, delay_reference_date(batch)))[1],
            delay_message=build_delay_message(item),
            rectification_item_id=rectification_by_progress_item.get(item.id),
            has_rectification=item.id in rectification_by_progress_item,
        )
        for item in delayed[:limit]
    ]
    return AnalyticsDelayedRankingResponse(batch_id=batch.id, rows=rows)


@router.get("/trend", response_model=AnalyticsTrendResponse)
def trend(
    project_id: int,
    calculation_profile_id: int | None = None,
    calculation_method: str | None = None,
    baseline_plan_id: int | None = None,
    db: Session = Depends(get_db),
) -> AnalyticsTrendResponse:
    project = get_project_or_404(project_id, db)
    profile = resolve_calculation_profile(db, project_id, calculation_profile_id)
    calculation_method = effective_calculation_method(project, calculation_method)
    rows = []
    for batch in list_published_batches(db, project_id):
        items = apply_time_based_progress(list_items(db, project_id, batch.id), batch)
        baseline = resolve_baseline_plan(db, project_id, baseline_plan_id)
        items = filter_items_by_baseline(items, baseline)
        actual_percent, actual_unit_mixed, actual_warning = aggregate_progress(items, profile, "actual_percent", calculation_method)
        planned_percent, planned_unit_mixed, planned_warning = aggregate_progress(items, profile, "planned_percent", calculation_method)
        time_planned_percent, _, _ = aggregate_progress(items, profile, "time_planned_percent", calculation_method)
        imported_planned_percent, _, _ = aggregate_progress(items, profile, "imported_planned_percent", calculation_method)
        deviation = round(actual_percent - planned_percent, 4) if actual_percent is not None and planned_percent is not None else None
        rows.append(
            AnalyticsTrendPoint(
                batch_id=batch.id,
                sheet_name=batch.sheet_name,
                status=batch.status,
                is_frozen=batch.is_frozen,
                data_date=batch.data_date,
                published_at=batch.published_at,
                baseline_plan_id=batch.baseline_plan_id,
                baseline_plan_name=baseline_name(db, project_id, batch.baseline_plan_id),
                actual_percent=actual_percent,
                planned_percent=planned_percent,
                time_planned_percent=time_planned_percent,
                imported_planned_percent=imported_planned_percent,
                progress_deviation=deviation,
                item_count=len(items),
                unit_mixed=actual_unit_mixed or planned_unit_mixed,
                warning=actual_warning or planned_warning,
            )
        )
    return AnalyticsTrendResponse(calculation_profile_id=profile.id if profile else None, rows=rows)


@router.get("/baseline-comparison", response_model=BaselineComparisonResponse)
def baseline_comparison(
    project_id: int,
    batch_id: int | None = None,
    baseline_plan_id: int | None = None,
    db: Session = Depends(get_db),
) -> BaselineComparisonResponse:
    get_project_or_404(project_id, db)
    batch = get_published_batch(db, project_id, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Published import batch not found")
    meta = baseline_context(db, project_id, batch, baseline_plan_id)
    notice = meta["baseline_notice"] or "当前暂无基线对比数据。"
    has_comparable_data = bool(meta["batch_bound_baseline_plan_id"] or meta["current_view_baseline_plan_id"])
    if not has_comparable_data:
        notice = "当前暂无基线对比数据。"
    return BaselineComparisonResponse(
        batch_id=batch.id,
        batch_bound_baseline_plan_id=meta["batch_bound_baseline_plan_id"],
        batch_bound_baseline_plan_name=meta["batch_bound_baseline_plan_name"],
        current_view_baseline_plan_id=meta["current_view_baseline_plan_id"],
        current_view_baseline_plan_name=meta["current_view_baseline_plan_name"],
        is_consistent=bool(meta["baseline_consistent"]),
        notice=str(notice),
        has_comparable_data=has_comparable_data,
    )


@router.get("/data-quality", response_model=AnalyticsDataQualityResponse)
def data_quality(project_id: int, batch_id: int | None = None, db: Session = Depends(get_db)) -> AnalyticsDataQualityResponse:
    get_project_or_404(project_id, db)
    batch = get_published_batch(db, project_id, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Published import batch not found")
    issue_code_counts = [
        ValidationIssueCodeCount(code=code or "UNKNOWN", level=level, count=count)
        for code, level, count in db.execute(
            select(
                ImportValidationIssue.code,
                ImportValidationIssue.level,
                func.count(ImportValidationIssue.id),
            )
            .where(ImportValidationIssue.batch_id == batch.id)
            .group_by(ImportValidationIssue.code, ImportValidationIssue.level)
            .order_by(func.count(ImportValidationIssue.id).desc(), ImportValidationIssue.level, ImportValidationIssue.code)
        ).all()
    ]
    return AnalyticsDataQualityResponse(
        batch_id=batch.id,
        data_quality_score=batch.data_quality_score,
        field_completeness=batch.field_completeness,
        task_match_rate=batch.task_match_rate,
        valid_row_rate=batch.valid_row_rate,
        plan_field_completeness=batch.plan_field_completeness,
        unit_consistency=batch.unit_consistency,
        warning_count=batch.warning_count,
        error_count=batch.error_count,
        issue_code_counts=issue_code_counts,
        status=batch.status,
    )


@router.get("/insight", response_model=AnalyticsInsightResponse)
def insight(
    project_id: int,
    batch_id: int | None = None,
    calculation_profile_id: int | None = None,
    baseline_plan_id: int | None = None,
    building: str | None = None,
    db: Session = Depends(get_db),
) -> AnalyticsInsightResponse:
    get_project_or_404(project_id, db)
    try:
        return generate_progress_insight(
            db,
            project_id,
            batch_id=batch_id,
            calculation_profile_id=calculation_profile_id,
            baseline_plan_id=baseline_plan_id,
            building=building,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
