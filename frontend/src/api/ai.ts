import { request } from './http'
import type { AiCallLog, AiConfigPayload, AiConfigRead, AiInsightResponse, AiPromptTemplate } from '../types/ai'

export function getAiConfig(projectId: number) {
  return request<AiConfigRead>(`/api/projects/${projectId}/ai/config`)
}

export function updateAiConfig(projectId: number, payload: AiConfigPayload) {
  return request<AiConfigRead>(`/api/projects/${projectId}/ai/config`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function testAiConnection(projectId: number, payload: AiConfigPayload) {
  return request<{ success: boolean; message: string }>(`/api/projects/${projectId}/ai/test-connection`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function generateAiInsight(
  projectId: number,
  payload: {
    batch_id?: number | null
    calculation_profile_id?: number | null
    baseline_plan_id?: number | null
    building?: string | null
    mode: 'dashboard_summary' | 'weekly_report_text' | 'delay_reason_analysis' | 'rectification_suggestions'
  },
) {
  return request<AiInsightResponse>(`/api/projects/${projectId}/ai/insight`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function generateRectificationSuggestion(projectId: number, itemId: number) {
  return request<AiInsightResponse>(`/api/projects/${projectId}/ai/rectifications/${itemId}/suggestion`, {
    method: 'POST',
  })
}

export function generateWeeklyAiPreview(
  projectId: number,
  payload: {
    batch_id?: number | null
    calculation_profile_id?: number | null
    baseline_plan_id?: number | null
    building?: string | null
  },
) {
  return request<AiInsightResponse>(`/api/projects/${projectId}/ai/weekly-preview`, {
    method: 'POST',
    body: JSON.stringify({ ...payload, mode: 'weekly_report_text' }),
  })
}

export function listAiPromptTemplates(projectId: number) {
  return request<AiPromptTemplate[]>(`/api/projects/${projectId}/ai/templates`)
}

export function createAiPromptTemplate(projectId: number, payload: Partial<AiPromptTemplate>) {
  return request<AiPromptTemplate>(`/api/projects/${projectId}/ai/templates`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function copyAiPromptTemplate(projectId: number, templateId: number) {
  return request<AiPromptTemplate>(`/api/projects/${projectId}/ai/templates/${templateId}/copy`, {
    method: 'POST',
  })
}

export function updateAiPromptTemplate(projectId: number, templateId: number, payload: Partial<AiPromptTemplate>) {
  return request<AiPromptTemplate>(`/api/projects/${projectId}/ai/templates/${templateId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function deleteAiPromptTemplate(projectId: number, templateId: number) {
  return request<void>(`/api/projects/${projectId}/ai/templates/${templateId}`, {
    method: 'DELETE',
  })
}

export function listAiCallLogs(projectId: number) {
  return request<AiCallLog[]>(`/api/projects/${projectId}/ai/logs`)
}
