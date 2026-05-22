import { request } from './http'
import type {
  ProgressItem,
  ProgressItemEditHistory,
  ProgressItemFilterOptions,
  ProgressItemListResponse,
  ProgressItemPayload,
} from '../types/progressItem'

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

export function listProgressItems(
  projectId: number,
  params: {
    batchId?: number | null
    scope?: string | null
    dataDate?: string | null
    importGroupId?: string | null
    batchIds?: string | number[] | null
    constructionUnit?: string | null
    building?: string | null
    floor?: string | null
    discipline?: string | null
    systemName?: string | null
    status?: string | null
    keyword?: string | null
    page: number
    pageSize: number
  },
) {
  return request<ProgressItemListResponse>(
    withQuery(`/api/projects/${projectId}/progress-items`, {
      batch_id: params.batchId,
      scope: params.scope,
      data_date: params.dataDate,
      import_group_id: params.importGroupId,
      batch_ids: Array.isArray(params.batchIds) ? params.batchIds.join(',') : params.batchIds,
      construction_unit: params.constructionUnit,
      building: params.building,
      floor: params.floor,
      discipline: params.discipline,
      system_name: params.systemName,
      status: params.status,
      keyword: params.keyword,
      page: params.page,
      page_size: params.pageSize,
    }),
  )
}

export function listProgressItemFilterOptions(
  projectId: number,
  params: {
    batchId?: number | null
    scope?: string | null
    dataDate?: string | null
    importGroupId?: string | null
    batchIds?: string | number[] | null
  },
) {
  return request<ProgressItemFilterOptions>(
    withQuery(`/api/projects/${projectId}/progress-items/filter-options`, {
      batch_id: params.batchId,
      scope: params.scope,
      data_date: params.dataDate,
      import_group_id: params.importGroupId,
      batch_ids: Array.isArray(params.batchIds) ? params.batchIds.join(',') : params.batchIds,
    }),
  )
}

export function updateProgressItem(itemId: number, payload: ProgressItemPayload) {
  return request<ProgressItem>(`/api/progress-items/${itemId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function getProgressItemHistory(itemId: number) {
  return request<ProgressItemEditHistory[]>(`/api/progress-items/${itemId}/edit-history`)
}

export function undoLastProgressItemEdit(itemId: number) {
  return request<ProgressItem>(`/api/progress-items/${itemId}/undo-last-edit`, {
    method: 'POST',
  })
}
