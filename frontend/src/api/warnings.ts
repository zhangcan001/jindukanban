import { apiBaseUrl, buildApiError, normalizeNetworkError, request } from './http'
import type { WarningFilterOptions, WarningFilters, WarningRecord, WarningRule, WarningRulePayload, WarningRunResponse } from '../types/warning'

function withQuery(path: string, params: Record<string, string | number | boolean | null | undefined>) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  })
  const query = search.toString()
  return query ? `${path}?${query}` : path
}

export function listWarningRules(projectId: number) {
  return request<WarningRule[]>(`/api/projects/${projectId}/warning-rules`)
}

export function createWarningRule(projectId: number, payload: WarningRulePayload) {
  return request<WarningRule>(`/api/projects/${projectId}/warning-rules`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateWarningRule(ruleId: number, payload: Partial<WarningRulePayload>) {
  return request<WarningRule>(`/api/warning-rules/${ruleId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteWarningRule(ruleId: number) {
  return request<void>(`/api/warning-rules/${ruleId}`, { method: 'DELETE' })
}

export function runWarnings(projectId: number, batchId?: number | null) {
  return request<WarningRunResponse>(withQuery(`/api/projects/${projectId}/warnings/run`, { batch_id: batchId }), {
    method: 'POST',
  })
}

export function listWarnings(projectId: number, batchId?: number | null, unresolvedOnly = false, filters: WarningFilters = {}) {
  return request<WarningRecord[]>(
    withQuery(`/api/projects/${projectId}/warnings`, {
      batch_id: batchId,
      unresolved_only: unresolvedOnly,
      discipline: filters.discipline,
      building: filters.building,
      floor: filters.floor,
      level: filters.level,
      status: filters.status,
      keyword: filters.keyword,
    }),
  )
}

export function listWarningFilterOptions(projectId: number, batchId?: number | null) {
  return request<WarningFilterOptions>(
    withQuery(`/api/projects/${projectId}/warnings/filter-options`, { batch_id: batchId }),
  )
}

export async function exportWarnings(projectId: number, batchId?: number | null, unresolvedOnly = false, filters: WarningFilters = {}) {
  const path = withQuery(`/api/projects/${projectId}/warnings/export`, {
    batch_id: batchId,
    unresolved_only: unresolvedOnly,
    discipline: filters.discipline,
    building: filters.building,
    floor: filters.floor,
    level: filters.level,
    status: filters.status,
    keyword: filters.keyword,
  })
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}${path}`)
  } catch (error) {
    throw normalizeNetworkError(error)
  }
  if (!response.ok) {
    throw await buildApiError(response)
  }
  return response.blob()
}
