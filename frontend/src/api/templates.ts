import { request } from './http'
import type { MappingTemplate, MappingTemplatePayload, ProjectTemplate, ProjectTemplatePayload } from '../types/template'

export function listProjectTemplates() {
  return request<ProjectTemplate[]>('/api/templates/project-templates')
}

export function updateProjectTemplate(templateId: number, payload: ProjectTemplatePayload) {
  return request<ProjectTemplate>(`/api/templates/project-templates/${templateId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function copyProjectTemplate(templateId: number) {
  return request<ProjectTemplate>(`/api/templates/project-templates/${templateId}/copy`, {
    method: 'POST',
  })
}

export function deleteProjectTemplate(templateId: number) {
  return request<void>(`/api/templates/project-templates/${templateId}`, {
    method: 'DELETE',
  })
}

export function listMappingTemplates() {
  return request<MappingTemplate[]>('/api/templates/mapping-templates')
}

export function updateMappingTemplate(templateId: number, payload: MappingTemplatePayload) {
  return request<MappingTemplate>(`/api/templates/mapping-templates/${templateId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteMappingTemplate(templateId: number) {
  return request<void>(`/api/templates/mapping-templates/${templateId}`, {
    method: 'DELETE',
  })
}
