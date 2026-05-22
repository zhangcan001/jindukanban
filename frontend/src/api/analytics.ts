import { request } from './http'
import type {
  AnalyticsDataQualityResponse,
  AnalyticsBuildingFloorResponse,
  AnalyticsDelayedRankingResponse,
  AnalyticsFieldsResponse,
  AnalyticsGroupByResponse,
  AnalyticsInsightResponse,
  AnalyticsOverviewResponse,
  AnalyticsPlanVsActualResponse,
  AnalyticsTrendResponse,
  BaselineComparisonResponse,
  DashboardV2Response,
  DashboardUnifiedResponse,
  ProjectOverviewResponse,
} from '../types/analytics'

function withQuery(path: string, params: Record<string, string | number | null | undefined>) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  })
  const query = search.toString()
  return query ? `${path}?${query}` : path
}

export function getAnalyticsFields(projectId: number, batchId?: number | null) {
  return request<AnalyticsFieldsResponse>(withQuery(`/api/projects/${projectId}/analytics/fields`, { batch_id: batchId }))
}

export function getAnalyticsOverview(projectId: number, batchId?: number | null, calculationProfileId?: number | null) {
  return getAnalyticsOverviewWithBaseline(projectId, batchId, calculationProfileId, null)
}

export function getAnalyticsOverviewWithBaseline(
  projectId: number,
  batchId?: number | null,
  calculationProfileId?: number | null,
  baselinePlanId?: number | null,
  calculationMethod?: string | null,
) {
  return request<AnalyticsOverviewResponse>(
    withQuery(`/api/projects/${projectId}/analytics/overview`, {
      batch_id: batchId,
      calculation_profile_id: calculationProfileId,
      baseline_plan_id: baselinePlanId,
      calculation_method: calculationMethod,
    }),
  )
}

export function getProjectOverview(projectId: number, calculationProfileId?: number | null, calculationMethod?: string | null) {
  return request<ProjectOverviewResponse>(
    withQuery(`/api/projects/${projectId}/analytics/project-overview`, {
      calculation_profile_id: calculationProfileId,
      calculation_method: calculationMethod,
    }),
  )
}

export function getAnalyticsGroupBy(
  projectId: number,
  params: {
    batchId?: number | null
    dimension: string
    metric: string
    aggregation: string
    calculationProfileId?: number | null
    baselinePlanId?: number | null
    calculationMethod?: string | null
  },
) {
  return request<AnalyticsGroupByResponse>(
    withQuery(`/api/projects/${projectId}/analytics/group-by`, {
      batch_id: params.batchId,
      dimension: params.dimension,
      metric: params.metric,
      aggregation: params.aggregation,
      calculation_profile_id: params.calculationProfileId,
      baseline_plan_id: params.baselinePlanId,
      calculation_method: params.calculationMethod,
    }),
  )
}

export function getAnalyticsPlanVsActual(
  projectId: number,
  batchId?: number | null,
  dimension = 'discipline',
  calculationProfileId?: number | null,
  baselinePlanId?: number | null,
  calculationMethod?: string | null,
) {
  return request<AnalyticsPlanVsActualResponse>(
    withQuery(`/api/projects/${projectId}/analytics/plan-vs-actual`, {
      batch_id: batchId,
      dimension,
      calculation_profile_id: calculationProfileId,
      baseline_plan_id: baselinePlanId,
      calculation_method: calculationMethod,
    }),
  )
}

export function getAnalyticsBuildingFloor(
  projectId: number,
  params: {
    batchId?: number | null
    building?: string | null
    calculationProfileId?: number | null
    baselinePlanId?: number | null
    calculationMethod?: string | null
  },
) {
  return request<AnalyticsBuildingFloorResponse>(
    withQuery(`/api/projects/${projectId}/analytics/building-floor`, {
      batch_id: params.batchId,
      building: params.building,
      calculation_profile_id: params.calculationProfileId,
      baseline_plan_id: params.baselinePlanId,
      calculation_method: params.calculationMethod,
    }),
  )
}

export function getAnalyticsDelayedRanking(projectId: number, batchId?: number | null, limit = 20, baselinePlanId?: number | null) {
  return request<AnalyticsDelayedRankingResponse>(
    withQuery(`/api/projects/${projectId}/analytics/delayed-ranking`, {
      batch_id: batchId,
      limit,
      baseline_plan_id: baselinePlanId,
    }),
  )
}

export function getAnalyticsTrend(projectId: number, calculationProfileId?: number | null, baselinePlanId?: number | null, calculationMethod?: string | null) {
  return request<AnalyticsTrendResponse>(
    withQuery(`/api/projects/${projectId}/analytics/trend`, {
      calculation_profile_id: calculationProfileId,
      baseline_plan_id: baselinePlanId,
      calculation_method: calculationMethod,
    }),
  )
}

export function getAnalyticsDataQuality(projectId: number, batchId?: number | null) {
  return request<AnalyticsDataQualityResponse>(withQuery(`/api/projects/${projectId}/analytics/data-quality`, { batch_id: batchId }))
}

export function getAnalyticsInsight(
  projectId: number,
  params: {
    batchId?: number | null
    calculationProfileId?: number | null
    baselinePlanId?: number | null
    building?: string | null
  },
) {
  return request<AnalyticsInsightResponse>(
    withQuery(`/api/projects/${projectId}/analytics/insight`, {
      batch_id: params.batchId,
      calculation_profile_id: params.calculationProfileId,
      baseline_plan_id: params.baselinePlanId,
      building: params.building,
    }),
  )
}

export function getBaselineComparison(projectId: number, batchId?: number | null, baselinePlanId?: number | null) {
  return request<BaselineComparisonResponse>(
    withQuery(`/api/projects/${projectId}/analytics/baseline-comparison`, {
      batch_id: batchId,
      baseline_plan_id: baselinePlanId,
    }),
  )
}

export function getDashboardUnified(
  projectId: number,
  params: {
    dataDate?: string | null
    importGroupId?: string | null
    batchId?: number | null
    sheetName?: string | null
    constructionUnit?: string | null
    building?: string | null
    floor?: string | null
    discipline?: string | null
    systemName?: string | null
    status?: string | null
    calculationProfileId?: number | null
    baselinePlanId?: number | null
    calculationMethod?: string | null
  },
) {
  return request<DashboardUnifiedResponse>(
    withQuery(`/api/projects/${projectId}/analytics/dashboard-unified`, {
      data_date: params.dataDate,
      import_group_id: params.importGroupId,
      batch_id: params.batchId,
      sheet_name: params.sheetName,
      construction_unit: params.constructionUnit,
      building: params.building,
      floor: params.floor,
      discipline: params.discipline,
      system_name: params.systemName,
      status: params.status,
      calculation_profile_id: params.calculationProfileId,
      baseline_plan_id: params.baselinePlanId,
      calculation_method: params.calculationMethod,
    }),
  )
}

export function getDashboardV2(
  projectId: number,
  params: {
    viewMode?: 'overview' | 'discipline' | 'building'
    dataDate?: string | null
    importGroupId?: string | null
    batchId?: number | null
    sheetName?: string | null
    constructionUnit?: string | null
    building?: string | null
    floor?: string | null
    discipline?: string | null
    systemName?: string | null
    status?: string | null
    calculationProfileId?: number | null
    baselinePlanId?: number | null
    calculationMethod?: string | null
  },
) {
  return request<DashboardV2Response>(
    withQuery(`/api/projects/${projectId}/dashboard-v2`, {
      view_mode: params.viewMode,
      data_date: params.dataDate,
      import_group_id: params.importGroupId,
      batch_id: params.batchId,
      sheet_name: params.sheetName,
      construction_unit: params.constructionUnit,
      building: params.building,
      floor: params.floor,
      discipline: params.discipline,
      system_name: params.systemName,
      status: params.status,
      calculation_profile_id: params.calculationProfileId,
      baseline_plan_id: params.baselinePlanId,
      calculation_method: params.calculationMethod,
    }),
  )
}
