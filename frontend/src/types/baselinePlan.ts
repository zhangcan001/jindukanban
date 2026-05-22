export type BaselinePlan = {
  id: number
  project_id: number
  name: string
  plan_type: string
  description?: string | null
  baseline_date?: string | null
  is_default: boolean
  is_active: boolean
  bound_batch_count: number
  latest_bound_batch_date?: string | null
  created_at: string
  updated_at: string
}

export type BaselinePlanPayload = Omit<BaselinePlan, 'id' | 'project_id' | 'bound_batch_count' | 'latest_bound_batch_date' | 'created_at' | 'updated_at'>

export type BaselineBoundBatch = {
  id: number
  project_id: number
  file_name: string
  sheet_name?: string | null
  data_date?: string | null
  status: string
  imported_count: number
  published_at?: string | null
  created_at: string
  baseline_plan_id?: number | null
  baseline_plan_name?: string | null
}
