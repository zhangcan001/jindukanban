import { apiBaseUrl, buildApiError, normalizeNetworkError, request } from './http'
import type {
  RectificationActionLog,
  RectificationFilterOptions,
  RectificationFilters,
  RectificationItem,
  RectificationListResponse,
  RectificationSummary,
} from '../types/rectification'

function withQuery(path: string, params: Record<string, string | number | boolean | null | undefined>) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') search.set(key, String(value))
  })
  const query = search.toString()
  return query ? `${path}?${query}` : path
}

export function listRectifications(projectId: number, filters: RectificationFilters = {}) {
  return request<RectificationListResponse>(withQuery(`/api/projects/${projectId}/rectifications`, filters))
}

export function getRectificationSummary(
  projectId: number,
  filters: number | null | Pick<RectificationFilters, 'scope' | 'batch_id' | 'data_date' | 'import_group_id' | 'batch_ids'> = {},
) {
  const params = typeof filters === 'number' || filters === null ? { batch_id: filters } : filters
  return request<RectificationSummary>(withQuery(`/api/projects/${projectId}/rectifications/summary`, params))
}

export function listRectificationFilterOptions(
  projectId: number,
  params: Pick<RectificationFilters, 'scope' | 'batch_id' | 'data_date' | 'import_group_id' | 'batch_ids'> = {},
) {
  return request<RectificationFilterOptions>(
    withQuery(`/api/projects/${projectId}/rectifications/filter-options`, params),
  )
}

export function updateRectification(projectId: number, id: number, payload: Partial<RectificationItem>) {
  return request<RectificationItem>(`/api/projects/${projectId}/rectifications/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function createRectification(projectId: number, payload: Partial<RectificationItem>) {
  return request<RectificationItem>(`/api/projects/${projectId}/rectifications`, {
    method: 'POST',
    body: JSON.stringify({ source_type: 'manual', ...payload }),
  })
}

export function batchUpdateRectifications(projectId: number, payload: Record<string, unknown>) {
  return request<{ updated_count: number; skipped_count: number; skipped_ids: number[] }>(
    `/api/projects/${projectId}/rectifications/batch-update`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export function createRectificationFromProgressItem(projectId: number, batchId: number, progressItemId: number) {
  return request<{ item: RectificationItem; created: boolean; message: string }>(
    `/api/projects/${projectId}/rectifications/from-progress-items`,
    {
      method: 'POST',
      body: JSON.stringify({ batch_id: batchId, progress_item_id: progressItemId }),
    },
  )
}

export function createRectificationFromWarning(projectId: number, warningRecordId: number) {
  return request<{ item: RectificationItem; created: boolean; message: string }>(
    `/api/projects/${projectId}/rectifications/from-warnings`,
    {
      method: 'POST',
      body: JSON.stringify({ warning_record_id: warningRecordId }),
    },
  )
}

export function listRectificationLogs(projectId: number, id: number) {
  return request<RectificationActionLog[]>(`/api/projects/${projectId}/rectifications/${id}/logs`)
}

export async function exportRectifications(projectId: number, filters: RectificationFilters = {}) {
  const path = withQuery(`/api/projects/${projectId}/rectifications/export`, filters)
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}${path}`)
  } catch (error) {
    throw normalizeNetworkError(error)
  }
  if (!response.ok) throw await buildApiError(response)
  const disposition = response.headers.get('content-disposition') ?? ''
  const encodedName = /filename\*=utf-8''([^;]+)/i.exec(disposition)?.[1]
  const matchedName = /filename="?([^"]+)"?/i.exec(disposition)?.[1]
  const fileName = encodedName ? decodeURIComponent(encodedName) : decodeURIComponent(matchedName || '整改跟踪表.xlsx')
  const blobUrl = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = blobUrl
  link.download = fileName
  link.click()
  URL.revokeObjectURL(blobUrl)
  return fileName
}
