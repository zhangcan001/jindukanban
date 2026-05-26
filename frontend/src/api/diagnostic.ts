import { request } from './http'

export type DiagnosticLogEntry = {
  ts: string
  level: string
  logger: string
  message: string
  request_id?: string | null
  exc_info?: string | null
  extra?: Record<string, unknown>
}

export type DiagnosticRecentLogs = {
  total: number
  entries: DiagnosticLogEntry[]
}

export type DiagnosticSystemInfo = {
  app_name: string
  app_env: string
  log_level: string
  log_format: string
  python_version: string
  platform: string
  pid: number
}

export function getRecentErrors(params: { level?: string; limit?: number } = {}) {
  const search = new URLSearchParams()
  if (params.level) search.set('level', params.level)
  if (params.limit) search.set('limit', String(params.limit))
  const query = search.toString()
  return request<DiagnosticRecentLogs>(`/api/diagnostic/recent-errors${query ? `?${query}` : ''}`)
}

export function clearDiagnosticLogs() {
  return request<{ cleared: number }>(`/api/diagnostic/clear-logs`, { method: 'POST' })
}

export function getSystemInfo() {
  return request<DiagnosticSystemInfo>(`/api/diagnostic/system-info`)
}
