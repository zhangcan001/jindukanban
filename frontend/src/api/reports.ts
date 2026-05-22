import { apiBaseUrl, buildApiError, normalizeNetworkError, request } from './http'
import type { DelayRectificationFilters, ReportConfig, ReportExportRecord, ReportHistoryFilters, ReportPreview, ReportType } from '../types/report'

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

export function listReportExports(projectId: number, filters: ReportHistoryFilters = {}) {
  const path = withQuery(`/api/projects/${projectId}/reports/exports`, {
    report_type: filters.reportType,
    project_name: filters.projectName,
    date_from: filters.dateFrom,
    date_to: filters.dateTo,
    keyword: filters.keyword,
  })
  return request<ReportExportRecord[]>(path)
}

export function getReportConfig(projectId: number) {
  return request<ReportConfig>(`/api/projects/${projectId}/reports/config`)
}

export function updateReportConfig(projectId: number, payload: ReportConfig) {
  return request<ReportConfig>(`/api/projects/${projectId}/reports/config`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function previewReport(
  projectId: number,
  reportType: ReportType,
  batchId?: number | null,
  calculationProfileId?: number | null,
  baselinePlanId?: number | null,
) {
  const path = withQuery(`/api/projects/${projectId}/reports/preview/${reportType}`, {
    batch_id: batchId,
    calculation_profile_id: calculationProfileId,
    baseline_plan_id: baselinePlanId,
  })
  return request<ReportPreview>(path)
}

function downloadBlob(blob: Blob, disposition: string, fallbackName: string) {
  const encodedName = /filename\*=utf-8''([^;]+)/i.exec(disposition)?.[1]
  const matchedName = /filename="?([^"]+)"?/i.exec(disposition)?.[1]
  const fileName = encodedName ? decodeURIComponent(encodedName) : decodeURIComponent(matchedName || fallbackName)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  link.click()
  URL.revokeObjectURL(url)
  return fileName
}

async function fetchDownload(path: string, fallbackName: string) {
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}${path}`)
  } catch (error) {
    throw normalizeNetworkError(error)
  }
  if (!response.ok) {
    throw await buildApiError(response)
  }
  return downloadBlob(await response.blob(), response.headers.get('content-disposition') ?? '', fallbackName)
}

export async function exportReport(projectId: number, reportType: ReportType, batchId?: number | null, calculationProfileId?: number | null) {
  return exportReportWithBaseline(projectId, reportType, batchId, calculationProfileId, null)
}

export async function exportReportWithBaseline(
  projectId: number,
  reportType: ReportType,
  batchId?: number | null,
  calculationProfileId?: number | null,
  baselinePlanId?: number | null,
  useAiText = false,
) {
  if (reportType === 'dashboard_excel') {
    return exportDashboardReport(projectId, batchId, calculationProfileId, baselinePlanId)
  }
  if (reportType === 'weekly_word') {
    return exportWeeklyWordReport(projectId, batchId, calculationProfileId, baselinePlanId, null, useAiText)
  }
  if (reportType === 'weekly_pdf') {
    return exportWeeklyPdfReport(projectId, batchId, calculationProfileId, baselinePlanId)
  }
  if (reportType === 'delay_rectification_excel') {
    return exportDelayRectificationReport(projectId, batchId, calculationProfileId, baselinePlanId)
  }
  if (reportType === 'rectification_tracking') {
    const path = withQuery(`/api/projects/${projectId}/rectifications/export`, { batch_id: batchId })
    return fetchDownload(path, '整改跟踪表.xlsx')
  }
  if (reportType === 'maintenance_report') {
    const path = `/api/maintenance/data-health`
    const data = await request<unknown>(path)
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' })
    return downloadBlob(blob, '', '数据维护报告.json')
  }
  const path = withQuery(`/api/projects/${projectId}/reports/${reportType}`, {
    batch_id: batchId,
    calculation_profile_id: calculationProfileId,
    baseline_plan_id: baselinePlanId,
  })
  return fetchDownload(path, `${reportType}.xlsx`)
}

export async function exportDashboardReport(
  projectId: number,
  batchId?: number | null,
  calculationProfileId?: number | null,
    baselinePlanId?: number | null,
    building?: string | null,
  filters: {
    constructionUnit?: string | null
    discipline?: string | null
    floor?: string | null
    systemName?: string | null
    delayLevel?: string | null
    metric?: string | null
    calculationMethod?: string | null
    scope?: string | null
    dataDate?: string | null
    importGroupId?: string | null
    batchIds?: string | null
  } = {},
) {
  const path = withQuery(`/api/projects/${projectId}/reports/dashboard-export`, {
    batch_id: batchId,
    calculation_profile_id: calculationProfileId,
    baseline_plan_id: baselinePlanId,
    construction_unit: filters.constructionUnit,
    building,
    discipline: filters.discipline,
    floor: filters.floor,
    system_name: filters.systemName,
    delay_level: filters.delayLevel,
    metric: filters.metric,
    calculation_method: filters.calculationMethod,
    scope: filters.scope,
    data_date: filters.dataDate,
    import_group_id: filters.importGroupId,
    batch_ids: filters.batchIds,
    export_format: 'xlsx',
  })
  return fetchDownload(path, '当前看板.xlsx')
}

export async function exportWeeklyWordReport(
  projectId: number,
  batchId?: number | null,
  calculationProfileId?: number | null,
  baselinePlanId?: number | null,
  building?: string | null,
  useAiText = false,
  calculationMethod?: string | null,
) {
  const path = withQuery(`/api/projects/${projectId}/reports/weekly-word`, {
    batch_id: batchId,
    calculation_profile_id: calculationProfileId,
    baseline_plan_id: baselinePlanId,
    building,
    use_ai_text: useAiText ? 'true' : null,
    calculation_method: calculationMethod,
  })
  return fetchDownload(path, '进度周报.docx')
}

export async function exportWeeklyPdfReport(
  projectId: number,
  batchId?: number | null,
  calculationProfileId?: number | null,
  baselinePlanId?: number | null,
  building?: string | null,
  calculationMethod?: string | null,
) {
  const path = withQuery(`/api/projects/${projectId}/reports/weekly-pdf`, {
    batch_id: batchId,
    calculation_profile_id: calculationProfileId,
    baseline_plan_id: baselinePlanId,
    building,
    use_ai: 'false',
    calculation_method: calculationMethod,
  })
  return fetchDownload(path, '进度周报.pdf')
}

export async function exportDelayRectificationReport(
  projectId: number,
  batchId?: number | null,
  calculationProfileId?: number | null,
  baselinePlanId?: number | null,
  building?: string | null,
  filters: DelayRectificationFilters = {},
) {
  const path = withQuery(`/api/projects/${projectId}/reports/delay-rectification-export`, {
    batch_id: batchId,
    calculation_profile_id: calculationProfileId,
    baseline_plan_id: baselinePlanId,
    building: filters.building ?? building,
    discipline: filters.discipline,
    floor: filters.floor,
    delay_level: filters.delayLevel,
    calculation_method: filters.calculationMethod,
    format: 'xlsx',
  })
  return fetchDownload(path, '滞后项整改清单.xlsx')
}
