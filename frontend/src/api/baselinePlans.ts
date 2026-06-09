import { request } from './http'
import type {
  BaselineBoundBatch,
  BaselinePlan,
  BaselinePlanFromBatchPayload,
  BaselinePlanFromBatchResult,
  BaselinePlanPayload,
} from '../types/baselinePlan'

export function listBaselinePlans(projectId: number) {
  return request<BaselinePlan[]>(`/api/projects/${projectId}/baseline-plans`)
}

export function createBaselinePlan(projectId: number, payload: BaselinePlanPayload) {
  return request<BaselinePlan>(`/api/projects/${projectId}/baseline-plans`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function createBaselinePlanFromBatch(projectId: number, payload: BaselinePlanFromBatchPayload) {
  return request<BaselinePlanFromBatchResult>(`/api/projects/${projectId}/baseline-plans/from-current-batch`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateBaselinePlan(
  projectId: number,
  baselineId: number,
  payload: Partial<BaselinePlanPayload>,
) {
  return request<BaselinePlan>(`/api/projects/${projectId}/baseline-plans/${baselineId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function listBaselineBoundBatches(projectId: number, baselineId: number) {
  return request<BaselineBoundBatch[]>(`/api/projects/${projectId}/baseline-plans/${baselineId}/batches`)
}

export function deleteBaselinePlan(projectId: number, baselineId: number) {
  return request<void>(`/api/projects/${projectId}/baseline-plans/${baselineId}`, {
    method: 'DELETE',
  })
}
