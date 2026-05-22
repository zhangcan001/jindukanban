from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.validation import ValidationIssueCodeCount


class AnalyticsWarning(BaseModel):
    code: str
    message: str


class CalculationMethodRead(BaseModel):
    code: str
    name: str
    available: bool
    recommended: bool = False
    reason: str | None = None
    warning: str | None = None


class AnalyticsFieldsResponse(BaseModel):
    dimensions: list[str]
    metrics: list[str]
    aggregations: list[str]


class AnalyticsOverviewResponse(BaseModel):
    batch_id: int | None
    calculation_profile_id: int | None
    calculation_method: str | None = None
    calculation_method_name: str | None = None
    recommended_method: str | None = None
    statistics_algorithm: str | None = None
    statistics_label: str | None = None
    weight_source: str | None = None
    weight_count: int = 0
    weight_total: float | None = None
    is_weight_normalized: bool = False
    normalized_actual_progress: float | None = None
    normalized_planned_progress: float | None = None
    project_contribution_actual: float | None = None
    project_contribution_planned: float | None = None
    weight_warning: str | None = None
    recommendation_reason: str | None = None
    calculation_method_description: str | None = None
    available_methods: list[CalculationMethodRead] = []
    available_calculation_methods: list[CalculationMethodRead] = []
    mixed_units: bool = False
    unit_list: list[str] = []
    weight_sum: float | None = None
    included_batch_count: int = 0
    included_batches: list[ProjectOverviewBatch] = []
    baseline_plan_id: int | None = None
    baseline_plan_name: str | None = None
    batch_bound_baseline_plan_id: int | None = None
    batch_bound_baseline_plan_name: str | None = None
    current_view_baseline_plan_id: int | None = None
    current_view_baseline_plan_name: str | None = None
    baseline_consistent: bool = True
    baseline_notice: str | None = None
    item_count: int
    task_count: int
    actual_percent: float | None
    planned_percent: float | None
    actual_progress: float | None = None
    planned_progress: float | None = None
    time_planned_percent: float | None = None
    imported_planned_percent: float | None = None
    progress_deviation: float | None
    total_quantity: float | None
    actual_quantity: float | None
    remaining_quantity: float | None
    status_counts: dict[str, int]
    unit_mixed: bool = False
    warning: str | None = None
    warnings: list[AnalyticsWarning] = []
    batch_status_label: str | None = None
    batch_is_frozen: bool = False
    project_is_archived: bool = False


class ProjectOverviewBatch(BaseModel):
    batch_id: int
    sheet_name: str | None = None
    import_group_id: str | None = None
    import_group_name: str | None = None
    data_date: date | None = None
    actual_percent: float | None = None
    planned_percent: float | None = None
    item_count: int = 0


class ProjectOverviewResponse(BaseModel):
    project_actual_percent: float | None = None
    project_planned_percent: float | None = None
    project_deviation: float | None = None
    actual_progress: float | None = None
    planned_progress: float | None = None
    progress_deviation: float | None = None
    data_date: date | None = None
    included_batch_count: int = 0
    included_batches: list[ProjectOverviewBatch] = []
    calculation_method: str
    calculation_method_name: str | None = None
    recommended_method: str | None = None
    recommendation_reason: str | None = None
    available_methods: list[CalculationMethodRead] = []
    mixed_units: bool = False
    unit_list: list[str] = []
    statistics_label: str | None = None
    weight_sum: float | None = None
    item_count: int = 0
    task_count: int = 0
    is_project_aggregate: bool = True
    empty: bool = False
    message: str | None = None
    scope_label: str | None = None
    warning: str | None = None
    warnings: list[AnalyticsWarning] = []


class AnalyticsGroupRow(BaseModel):
    dimension_value: str | None
    value: float | int | None
    count: int
    units: list[str] = []
    unit_mixed: bool = False
    warning: str | None = None


class AnalyticsGroupByResponse(BaseModel):
    batch_id: int | None
    dimension: str
    metric: str
    aggregation: str
    rows: list[AnalyticsGroupRow]


class AnalyticsPlanVsActualRow(BaseModel):
    dimension_value: str | None
    actual_percent: float | None
    planned_percent: float | None
    time_planned_percent: float | None = None
    imported_planned_percent: float | None = None
    progress_deviation: float | None
    delayed_count: int = 0
    count: int
    units: list[str] = []
    unit_mixed: bool = False
    warning: str | None = None


class AnalyticsPlanVsActualResponse(BaseModel):
    batch_id: int | None
    dimension: str
    rows: list[AnalyticsPlanVsActualRow]


class DeviationAttributionRow(BaseModel):
    dimension_values: dict[str, str]
    actual_percent: float | None
    planned_percent: float | None
    progress_deviation: float | None
    abs_deviation: float | None
    delayed_count: int = 0
    count: int
    contribution: float | None = None
    warning: str | None = None


class DeviationAttributionResponse(BaseModel):
    batch_id: int | None
    dimensions: list[str]
    total_count: int
    overall_actual_percent: float | None = None
    overall_planned_percent: float | None = None
    overall_progress_deviation: float | None = None
    rows: list[DeviationAttributionRow]


class AnalyticsBuildingFloorItem(BaseModel):
    building: str
    floor: str
    task_count: int
    actual_percent: float | None
    planned_percent: float | None
    time_planned_percent: float | None = None
    imported_planned_percent: float | None = None
    progress_deviation: float | None
    delayed_count: int
    unit_mixed: bool = False
    units: list[str] = []
    warning: str | None = None


class AnalyticsBuildingFloorResponse(BaseModel):
    batch_id: int | None
    buildings: list[str]
    selected_building: str | None = None
    items: list[AnalyticsBuildingFloorItem]


class AnalyticsDelayedItem(BaseModel):
    id: int
    progress_item_id: int
    task_id: int | None
    task_name: str
    wbs_code: str | None
    task_code: str | None
    area: str | None
    construction_unit: str | None = None
    building: str
    floor: str
    discipline: str
    system_name: str
    unit: str | None
    actual_percent: float | None
    planned_percent: float | None
    time_planned_percent: float | None = None
    imported_planned_percent: float | None = None
    progress_deviation: float | None
    status: str | None
    delay_level: str
    delay_level_label: str
    delay_message: str
    rectification_item_id: int | None = None
    has_rectification: bool = False


class AnalyticsDelayedRankingResponse(BaseModel):
    batch_id: int | None
    rows: list[AnalyticsDelayedItem]


class AnalyticsTrendPoint(BaseModel):
    batch_id: int
    sheet_name: str | None = None
    status: str | None = None
    is_frozen: bool = False
    data_date: date | None
    published_at: datetime | None
    baseline_plan_id: int | None = None
    baseline_plan_name: str | None = None
    actual_percent: float | None
    planned_percent: float | None
    time_planned_percent: float | None = None
    imported_planned_percent: float | None = None
    progress_deviation: float | None
    schedule_phase: str | None = None
    item_count: int
    unit_mixed: bool = False
    warning: str | None = None


class AnalyticsTrendResponse(BaseModel):
    calculation_profile_id: int | None
    rows: list[AnalyticsTrendPoint]


class AnalyticsDataQualityResponse(BaseModel):
    batch_id: int | None
    data_quality_score: float | None
    field_completeness: float | None
    task_match_rate: float | None
    valid_row_rate: float | None
    plan_field_completeness: float | None
    unit_consistency: float | None
    warning_count: int
    error_count: int
    issue_code_counts: list[ValidationIssueCodeCount] = []
    status: str | None
    extra: dict[str, Any] = {}


class AnalyticsInsightResponse(BaseModel):
    overview_summary: str
    discipline_summary: str
    floor_summary: str
    building_floor_summary: str
    delay_summary: str
    quality_summary: str
    focus_points: list[str]
    recommended_actions: list[str]
    generated_at: str


class BaselineComparisonResponse(BaseModel):
    batch_id: int
    batch_bound_baseline_plan_id: int | None = None
    batch_bound_baseline_plan_name: str | None = None
    current_view_baseline_plan_id: int | None = None
    current_view_baseline_plan_name: str | None = None
    is_consistent: bool
    notice: str
    has_comparable_data: bool = True


class DashboardPlusDisciplineProgressRow(BaseModel):
    discipline: str
    task_count: int
    actual_percent: float | None = None
    planned_percent: float | None = None
    progress_deviation: float | None = None
    delayed_count: int = 0
    seriously_delayed_count: int = 0
    is_seriously_delayed: bool = False
    unit_mixed: bool = False
    units: list[str] = []
    warning: str | None = None


class DashboardPlusFloorDisciplineCell(BaseModel):
    floor: str
    discipline: str
    task_count: int
    actual_percent: float | None = None
    progress_deviation: float | None = None
    delayed_count: int = 0


class DashboardPlusBuildingDisciplineCell(BaseModel):
    building: str
    discipline: str
    task_count: int
    actual_percent: float | None = None
    delayed_count: int = 0


class DashboardPlusTaskDetail(BaseModel):
    id: int
    construction_unit: str | None = None
    building: str
    floor: str
    discipline: str
    task_name: str
    actual_percent: float | None = None
    planned_percent: float | None = None
    progress_deviation: float | None = None
    status: str | None = None
    delay_level: str
    delay_level_label: str


class DashboardPlusDelayStatusCount(BaseModel):
    status: str
    status_label: str
    count: int


class DashboardPlusDisciplineDelayCount(BaseModel):
    discipline: str
    seriously_delayed_count: int = 0
    delayed_count: int = 0
    slightly_delayed_count: int = 0
    normal_count: int = 0
    ahead_count: int = 0
    total_delayed_count: int = 0


class DashboardPlusDelayDistribution(BaseModel):
    status_counts: list[DashboardPlusDelayStatusCount] = []
    discipline_delay_counts: list[DashboardPlusDisciplineDelayCount] = []


class DashboardPlusResponse(BaseModel):
    batch_id: int | None = None
    filters: dict[str, str | None] = {}
    has_floor_data: bool = False
    has_building_data: bool = False
    discipline_progress: list[DashboardPlusDisciplineProgressRow] = []
    floor_discipline_matrix: list[DashboardPlusFloorDisciplineCell] = []
    building_discipline_matrix: list[DashboardPlusBuildingDisciplineCell] = []
    delay_distribution: DashboardPlusDelayDistribution = DashboardPlusDelayDistribution()
    task_details: list[DashboardPlusTaskDetail] = []


class DashboardUnifiedFilters(BaseModel):
    project_id: int
    data_date: date | None = None
    import_group_id: str | None = None
    batch_id: int | None = None
    sheet_name: str | None = None
    construction_unit: str | None = None
    building: str | None = None
    floor: str | None = None
    discipline: str | None = None
    system_name: str | None = None
    status: str | None = None
    calculation_method: str | None = None
    baseline_plan_id: int | None = None
    calculation_profile_id: int | None = None
    scope_label: str | None = None
    message: str | None = None


class DashboardUnifiedStatRow(BaseModel):
    name: str
    construction_unit: str | None = None
    building: str | None = None
    floor: str | None = None
    discipline: str | None = None
    system_name: str | None = None
    task_count: int = 0
    actual_percent: float | None = None
    planned_percent: float | None = None
    progress_deviation: float | None = None
    delayed_count: int = 0
    seriously_delayed_count: int = 0
    warning_count: int = 0
    rectification_count: int = 0
    calculation_method: str | None = None


class DashboardUnifiedMatrixRow(BaseModel):
    building: str | None = None
    floor: str | None = None
    discipline: str | None = None
    task_count: int = 0
    actual_percent: float | None = None
    planned_percent: float | None = None
    progress_deviation: float | None = None
    delayed_count: int = 0
    calculation_method: str | None = None


class DashboardBuildingElevationFloor(BaseModel):
    floor: str
    task_count: int = 0
    actual_percent: float | None = None
    planned_percent: float | None = None
    progress_deviation: float | None = None
    deviation: float | None = None
    delayed_count: int = 0
    serious_delayed_count: int = 0
    not_started_count: int = 0
    status: str = "no_data"
    status_label: str = "无数据"
    major_delayed_tasks: list[AnalyticsDelayedItem] = []
    calculation_method: str | None = None


class DashboardBuildingElevation(BaseModel):
    building: str
    floors: list[DashboardBuildingElevationFloor] = []
    task_count: int = 0
    actual_percent: float | None = None
    planned_percent: float | None = None
    progress_deviation: float | None = None
    status: str = "no_data"
    status_label: str = "无数据"
    message: str | None = None


class DashboardUnifiedDelayDistributionRow(BaseModel):
    status: str
    status_label: str
    count: int
    calculation_method: str | None = None


class DashboardUnifiedSummary(BaseModel):
    total: int = 0
    open: int = 0
    in_progress: int = 0
    completed: int = 0
    closed: int = 0
    overdue: int = 0
    unresolved: int = 0
    critical: int = 0
    warning: int = 0
    info: int = 0
    calculation_method: str | None = None


class DashboardUnifiedOptions(BaseModel):
    construction_units: list[str] = []
    buildings: list[str] = []
    floors: list[str] = []
    disciplines: list[str] = []
    systems: list[str] = []
    statuses: list[str] = []


class DashboardUnifiedResponse(BaseModel):
    filters: DashboardUnifiedFilters
    options: DashboardUnifiedOptions = DashboardUnifiedOptions()
    overview: AnalyticsOverviewResponse | None = None
    calculation_context: dict[str, Any] = {}
    by_construction_unit: list[DashboardUnifiedStatRow] = []
    by_building: list[DashboardUnifiedStatRow] = []
    by_floor: list[DashboardUnifiedStatRow] = []
    by_discipline: list[DashboardUnifiedStatRow] = []
    by_system: list[DashboardUnifiedStatRow] = []
    building_floor_matrix: list[DashboardUnifiedMatrixRow] = []
    building_elevation: list[DashboardBuildingElevation] = []
    discipline_floor_matrix: list[DashboardUnifiedMatrixRow] = []
    delay_distribution: list[DashboardUnifiedDelayDistributionRow] = []
    delayed_items: list[AnalyticsDelayedItem] = []
    warning_summary: DashboardUnifiedSummary = DashboardUnifiedSummary()
    rectification_summary: DashboardUnifiedSummary = DashboardUnifiedSummary()


class DashboardV2Scope(BaseModel):
    project_id: int
    view_mode: str = "overview"
    scope_label: str | None = None
    message: str | None = None
    filters: DashboardUnifiedFilters
    options: DashboardUnifiedOptions = DashboardUnifiedOptions()


class DashboardV2Response(BaseModel):
    scope: DashboardV2Scope
    overview: AnalyticsOverviewResponse | None = None
    discipline_cards: list[DashboardUnifiedStatRow] = []
    building_cards: list[DashboardUnifiedStatRow] = []
    floor_heatmap: list[DashboardUnifiedMatrixRow] = []
    building_elevation: list[DashboardBuildingElevation] = []
    delay_distribution: list[DashboardUnifiedDelayDistributionRow] = []
    delayed_items: list[AnalyticsDelayedItem] = []
    rectification_summary: DashboardUnifiedSummary = DashboardUnifiedSummary()
    calculation_context: dict[str, Any] = {}
    calculation_diagnostics: dict[str, Any] = {}
    dashboard_capabilities: dict[str, Any] = {}
