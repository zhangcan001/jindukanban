import { request } from './http'
import type { AboutRuntimeInfo, BackupRecord, BackupRestoreResponse, CleanupResponse, DataHealth, MaintenanceAiCallLog, MaintenanceLog, MaintenanceSummary, RuntimeStatus } from '../types/maintenance'

export function getMaintenanceSummary() {
  return request<MaintenanceSummary>('/api/maintenance/summary')
}

export function getRuntimeStatus() {
  return request<RuntimeStatus>('/api/maintenance/runtime-status')
}

export function getAboutRuntimeInfo() {
  return request<AboutRuntimeInfo>('/api/maintenance/about')
}

export function cleanupUnpublishedBatches(dryRun = false) {
  return request<CleanupResponse>(`/api/maintenance/cleanup-unpublished-batches?dry_run=${dryRun}`, {
    method: 'POST',
  })
}

export function cleanupTestProjects(dryRun = true) {
  return request<CleanupResponse>(`/api/maintenance/cleanup-test-projects?dry_run=${dryRun}`, {
    method: 'POST',
  })
}

export function getDataHealth() {
  return request<DataHealth>('/api/maintenance/data-health')
}

export function listBackupRecords() {
  return request<BackupRecord[]>('/api/maintenance/backups')
}

export function getBackupRecord(backupName: string) {
  return request<BackupRecord>(`/api/maintenance/backups/${encodeURIComponent(backupName)}`)
}

export function validateBackupRecord(backupName: string) {
  return request<BackupRecord>(`/api/maintenance/backups/${encodeURIComponent(backupName)}/validate`, {
    method: 'POST',
  })
}

export function restoreBackupRecord(backupName: string, confirmText: string) {
  return request<BackupRestoreResponse>(`/api/maintenance/backups/${encodeURIComponent(backupName)}/restore`, {
    method: 'POST',
    body: JSON.stringify({ confirm_text: confirmText }),
  })
}

export function listMaintenanceLogs(action?: string) {
  const query = action ? `?action=${encodeURIComponent(action)}` : ''
  return request<MaintenanceLog[]>(`/api/maintenance/logs${query}`)
}

export function getMaintenanceLog(logId: number) {
  return request<MaintenanceLog>(`/api/maintenance/logs/${logId}`)
}

export function listAiCallLogs() {
  return request<MaintenanceAiCallLog[]>('/api/maintenance/ai-logs')
}

export function safeCleanup(cleanupType: string, dryRun = true) {
  return request<CleanupResponse>('/api/maintenance/safe-cleanup', {
    method: 'POST',
    body: JSON.stringify({ cleanup_type: cleanupType, dry_run: dryRun }),
  })
}
