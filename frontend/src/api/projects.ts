import { request } from './http'
import type { Project, ProjectPayload } from '../types/project'

export function listProjects(includeArchived = false) {
  return request<Project[]>(`/api/projects?include_archived=${includeArchived}`)
}

export function getProject(projectId: number) {
  return request<Project>(`/api/projects/${projectId}`)
}

export function createProject(payload: ProjectPayload) {
  return request<Project>('/api/projects', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function createDemoProject() {
  return request<Project>('/api/projects/demo', {
    method: 'POST',
  })
}

export function updateProject(projectId: number, payload: Partial<ProjectPayload>) {
  return request<Project>(`/api/projects/${projectId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteProject(projectId: number) {
  return request<void>(`/api/projects/${projectId}`, {
    method: 'DELETE',
  })
}

export function forceDeleteProject(projectId: number, confirmText: string) {
  return request<{ deleted: boolean; project_id: number; deleted_counts: Record<string, number>; message: string }>(
    `/api/projects/${projectId}/force`,
    {
      method: 'DELETE',
      body: JSON.stringify({ confirm_text: confirmText }),
    },
  )
}

export function archiveProject(projectId: number, archiveRemark?: string | null) {
  return request<Project>(`/api/projects/${projectId}/archive`, {
    method: 'POST',
    body: JSON.stringify({ archive_remark: archiveRemark ?? null }),
  })
}

export function restoreProject(projectId: number) {
  return request<Project>(`/api/projects/${projectId}/restore`, {
    method: 'POST',
  })
}
