export type AnalyticsWarning = {
  code: string
  message: string
}

export type AnalyticsFieldsResponse = {
  dimensions: string[]
  metrics: string[]
  aggregations: string[]
}

export type CalculationMethodRead = {
  code: string
  name: string
  available: boolean
  recommended: boolean
  reason?: string | null
  warning?: string | null
}

export type AnalyticsOverviewResponse = {
  batch_id: number | null
  calculation_profile_id: number | null
  calculation_method?: string | null
  calculation_method_name?: string | null
  recommended_method?: string | null
  statistics_algorithm?: string | null
  statistics_label?: string | null
  weight_source?: string | null
  weight_count: number
  weight_total?: number | null
  is_weight_normalized: boolean
  normalized_actual_progress?: number | null
  normalized_planned_progress?: number | null
  project_contribution_actual?: number | null
  project_contribution_planned?: number | null
  weight_warning?: string | null
  recommendation_reason?: string | null
  calculation_method_description?: string | null
  available_methods?: CalculationMethodRead[]
  available_calculation_methods: CalculationMethodRead[]
  mixed_units?: boolean
  unit_list?: string[]
  weight_sum?: number | null
  included_batch_count?: number
  included_batches?: ProjectOverviewBatch[]
  baseline_plan_id?: number | null
  baseline_plan_name?: string | null
  batch_bound_baseline_plan_id?: number | null
  batch_bound_baseline_plan_name?: string | null
  current_view_baseline_plan_id?: number | null
  current_view_baseline_plan_name?: string | null
  baseline_consistent: boolean
  baseline_notice?: string | null
  item_count: number
  task_count: number
  actual_percent: number | null
  planned_percent: number | null
  actual_progress?: number | null
  planned_progress?: number | null
  time_planned_percent?: number | null
  imported_planned_percent?: number | null
  progress_deviation: number | null
  total_quantity: number | null
  actual_quantity: number | null
  remaining_quantity: number | null
  status_counts: Record<string, number>
  unit_mixed: boolean
  warning?: string | null
  warnings: AnalyticsWarning[]
  batch_status_label?: string | null
  batch_is_frozen: boolean
  project_is_archived: boolean
}

export type ProjectOverviewBatch = {
  batch_id: number
  sheet_name?: string | null
  import_group_id?: string | null
  import_group_name?: string | null
  data_date?: string | null
  actual_percent?: number | null
  planned_percent?: number | null
  item_count: number
}

export type ProjectOverviewResponse = {
  project_actual_percent?: number | null
  project_planned_percent?: number | null
  project_deviation?: number | null
  actual_progress?: number | null
  planned_progress?: number | null
  progress_deviation?: number | null
  data_date?: string | null
  included_batch_count: number
  included_batches: ProjectOverviewBatch[]
  calculation_method: string
  calculation_method_name?: string | null
  recommended_method?: string | null
  recommendation_reason?: string | null
  available_methods?: CalculationMethodRead[]
  mixed_units?: boolean
  unit_list?: string[]
  statistics_label?: string | null
  weight_sum?: number | null
  item_count: number
  task_count: number
  is_project_aggregate: boolean
  empty: boolean
  message?: string | null
  scope_label?: string | null
  warning?: string | null
  warnings: AnalyticsWarning[]
}

export type AnalyticsGroupRow = {
  dimension_value: string | null
  name?: string | null
  floor?: string | null
  value: number | null
  count: number
  task_count?: number
  actual_percent?: number | null
  planned_percent?: number | null
  progress_deviation?: number | null
  delayed_count?: number
  units: string[]
  unit_mixed: boolean
  warning?: string | null
}

export type AnalyticsGroupByResponse = {
  batch_id: number | null
  dimension: string
  metric: string
  aggregation: string
  rows: AnalyticsGroupRow[]
}

export type AnalyticsPlanVsActualRow = {
  dimension_value: string | null
  actual_percent: number | null
  planned_percent: number | null
  time_planned_percent?: number | null
  imported_planned_percent?: number | null
  progress_deviation: number | null
  delayed_count: number
  count: number
  units: string[]
  unit_mixed: boolean
  warning?: string | null
}

export type AnalyticsPlanVsActualResponse = {
  batch_id: number | null
  dimension: string
  rows: AnalyticsPlanVsActualRow[]
}

export type AnalyticsBuildingFloorItem = {
  building: string
  floor: string
  task_count: number
  actual_percent: number | null
  planned_percent: number | null
  time_planned_percent?: number | null
  imported_planned_percent?: number | null
  progress_deviation: number | null
  delayed_count: number
  unit_mixed: boolean
  units: string[]
  warning?: string | null
}

export type AnalyticsBuildingFloorResponse = {
  batch_id: number | null
  buildings: string[]
  selected_building?: string | null
  items: AnalyticsBuildingFloorItem[]
}

export type AnalyticsDelayedItem = {
  id: number
  progress_item_id: number
  task_id?: number | null
  task_name: string
  wbs_code?: string | null
  task_code?: string | null
  area?: string | null
  construction_unit?: string | null
  building: string
  floor: string
  discipline: string
  system_name: string
  unit?: string | null
  actual_percent?: number | null
  planned_percent?: number | null
  time_planned_percent?: number | null
  imported_planned_percent?: number | null
  progress_deviation?: number | null
  schedule_phase?: string | null
  status?: string | null
  delay_level: string
  delay_level_label: string
  delay_message: string
  rectification_item_id?: number | null
  has_rectification?: boolean
}

export type AnalyticsDelayedRankingResponse = {
  batch_id: number | null
  rows: AnalyticsDelayedItem[]
}

export type AnalyticsTrendPoint = {
  batch_id: number
  sheet_name?: string | null
  status?: string | null
  is_frozen: boolean
  data_date?: string | null
  published_at?: string | null
  baseline_plan_id?: number | null
  baseline_plan_name?: string | null
  actual_percent?: number | null
  planned_percent?: number | null
  progress_deviation?: number | null
  item_count: number
  unit_mixed: boolean
  warning?: string | null
}

export type AnalyticsTrendResponse = {
  calculation_profile_id: number | null
  rows: AnalyticsTrendPoint[]
}

export type AnalyticsDataQualityResponse = {
  batch_id: number | null
  data_quality_score?: number | null
  field_completeness?: number | null
  task_match_rate?: number | null
  valid_row_rate?: number | null
  plan_field_completeness?: number | null
  unit_consistency?: number | null
  warning_count: number
  error_count: number
  issue_code_counts: Array<{
    code: string
    level: string
    count: number
  }>
  status?: string | null
}

export type AnalyticsInsightResponse = {
  overview_summary: string
  discipline_summary: string
  floor_summary: string
  building_floor_summary: string
  delay_summary: string
  quality_summary: string
  focus_points: string[]
  recommended_actions: string[]
  generated_at: string
}

export type BaselineComparisonResponse = {
  batch_id: number
  batch_bound_baseline_plan_id?: number | null
  batch_bound_baseline_plan_name?: string | null
  current_view_baseline_plan_id?: number | null
  current_view_baseline_plan_name?: string | null
  is_consistent: boolean
  notice: string
  has_comparable_data: boolean
}

export type DashboardUnifiedFilters = {
  project_id: number
  data_date?: string | null
  import_group_id?: string | null
  batch_id?: number | null
  sheet_name?: string | null
  construction_unit?: string | null
  building?: string | null
  floor?: string | null
  discipline?: string | null
  system_name?: string | null
  status?: string | null
  calculation_method?: string | null
  baseline_plan_id?: number | null
  calculation_profile_id?: number | null
  scope_label?: string | null
  message?: string | null
}

export type DashboardUnifiedStatRow = {
  name: string
  construction_unit?: string | null
  building?: string | null
  floor?: string | null
  discipline?: string | null
  system_name?: string | null
  task_count: number
  actual_percent?: number | null
  planned_percent?: number | null
  progress_deviation?: number | null
  delayed_count: number
  seriously_delayed_count: number
  warning_count: number
  rectification_count: number
  calculation_method?: string | null
}

export type DashboardUnifiedMatrixRow = {
  building?: string | null
  floor?: string | null
  discipline?: string | null
  task_count: number
  actual_percent?: number | null
  planned_percent?: number | null
  progress_deviation?: number | null
  delayed_count: number
  calculation_method?: string | null
}

export type DashboardBuildingElevationFloor = {
  floor: string
  task_count: number
  actual_percent?: number | null
  planned_percent?: number | null
  progress_deviation?: number | null
  deviation?: number | null
  delayed_count: number
  serious_delayed_count: number
  not_started_count: number
  status: string
  status_label: string
  major_delayed_tasks: AnalyticsDelayedItem[]
  calculation_method?: string | null
}

export type DashboardBuildingElevation = {
  building: string
  floors: DashboardBuildingElevationFloor[]
  task_count: number
  actual_percent?: number | null
  planned_percent?: number | null
  progress_deviation?: number | null
  status: string
  status_label: string
  message?: string | null
}

export type DashboardUnifiedSummary = {
  total: number
  open: number
  in_progress: number
  completed: number
  closed: number
  overdue: number
  unresolved: number
  critical: number
  warning: number
  info: number
  calculation_method?: string | null
}

export type DashboardUnifiedResponse = {
  filters: DashboardUnifiedFilters
  options: {
    construction_units: string[]
    buildings: string[]
    floors: string[]
    disciplines: string[]
    systems: string[]
    statuses: string[]
  }
  overview?: AnalyticsOverviewResponse | null
  calculation_context: Record<string, unknown>
  by_construction_unit: DashboardUnifiedStatRow[]
  by_building: DashboardUnifiedStatRow[]
  by_floor: DashboardUnifiedStatRow[]
  by_discipline: DashboardUnifiedStatRow[]
  by_system: DashboardUnifiedStatRow[]
  building_floor_matrix: DashboardUnifiedMatrixRow[]
  building_elevation: DashboardBuildingElevation[]
  discipline_floor_matrix: DashboardUnifiedMatrixRow[]
  delay_distribution: Array<{ status: string; status_label: string; count: number; calculation_method?: string | null }>
  delayed_items: AnalyticsDelayedItem[]
  warning_summary: DashboardUnifiedSummary
  rectification_summary: DashboardUnifiedSummary
}

export type DashboardV2Scope = {
  project_id: number
  view_mode: 'overview' | 'discipline' | 'building'
  scope_label?: string | null
  message?: string | null
  filters: DashboardUnifiedFilters
  options: DashboardUnifiedResponse['options']
}

export type DashboardV2Response = {
  scope: DashboardV2Scope
  overview?: AnalyticsOverviewResponse | null
  discipline_cards: DashboardUnifiedStatRow[]
  building_cards: DashboardUnifiedStatRow[]
  floor_heatmap: DashboardUnifiedMatrixRow[]
  building_elevation: DashboardBuildingElevation[]
  delay_distribution: Array<{ status: string; status_label: string; count: number; calculation_method?: string | null }>
  delayed_items: AnalyticsDelayedItem[]
  rectification_summary: DashboardUnifiedSummary
  calculation_context: Record<string, unknown>
  calculation_diagnostics: Record<string, unknown>
  dashboard_capabilities: Record<string, { available: boolean; reason: string }>
}
