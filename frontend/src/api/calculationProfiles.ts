import { request } from './http'
import type { CalculationProfile, CalculationProfilePayload } from '../types/calculationProfile'

export function listCalculationProfiles(projectId: number) {
  return request<CalculationProfile[]>(`/api/projects/${projectId}/calculation-profiles`)
}

export function createCalculationProfile(projectId: number, payload: CalculationProfilePayload) {
  return request<CalculationProfile>(`/api/projects/${projectId}/calculation-profiles`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateCalculationProfile(
  projectId: number,
  profileId: number,
  payload: Partial<CalculationProfilePayload>,
) {
  return request<CalculationProfile>(`/api/projects/${projectId}/calculation-profiles/${profileId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteCalculationProfile(projectId: number, profileId: number) {
  return request<void>(`/api/projects/${projectId}/calculation-profiles/${profileId}`, {
    method: 'DELETE',
  })
}

