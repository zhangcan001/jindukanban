export type ProgressItem = {
  id: number
  project_id: number
  batch_id: number
  task_id?: number | null
  baseline_plan_id?: number | null
  wbs_code?: string | null
  task_code?: string | null
  task_name?: string | null
  area?: string | null
  construction_unit?: string | null
  building?: string | null
  floor?: string | null
  discipline?: string | null
  system_name?: string | null
  unit?: string | null
  total_quantity?: number | null
  planned_quantity?: number | null
  period_quantity?: number | null
  cumulative_quantity?: number | null
  actual_quantity?: number | null
  remaining_quantity?: number | null
  planned_percent?: number | null
  imported_planned_percent?: number | null
  actual_percent?: number | null
  reported_percent?: number | null
  time_planned_percent?: number | null
  progress_deviation?: number | null
  schedule_phase?: string | null
  current_period_quantity?: number | null
  current_period_percent?: number | null
  planned_start_date?: string | null
  planned_finish_date?: string | null
  actual_start_date?: string | null
  actual_finish_date?: string | null
  weight?: number | null
  value_amount?: number | null
  status?: string | null
  remark?: string | null
  extra_fields?: string | null
  is_manually_edited: boolean
  manual_edit_reason?: string | null
  created_at: string
  updated_at: string
}

export type ProgressItemListResponse = {
  items: ProgressItem[]
  total: number
  page: number
  page_size: number
  scope_info?: ProgressItemScopeInfo | null
}

export type ProgressItemScopeInfo = {
  scope: 'project' | 'batch' | string
  data_date?: string | null
  import_group_id?: string | null
  included_batch_ids: number[]
  included_sheets: string[]
  task_count: number
  message?: string | null
}

export type ProgressItemPayload = {
  reason: string
  actual_quantity?: number | null
  cumulative_quantity?: number | null
  period_quantity?: number | null
  planned_quantity?: number | null
  total_quantity?: number | null
  actual_percent?: number | null
  planned_percent?: number | null
  reported_percent?: number | null
  remaining_quantity?: number | null
  planned_start_date?: string | null
  planned_finish_date?: string | null
  actual_start_date?: string | null
  actual_finish_date?: string | null
  weight?: number | null
  value_amount?: number | null
  status?: string | null
  remark?: string | null
}

export type ProgressItemEditHistory = {
  id: number
  progress_item_id: number
  field_name: string
  old_value?: string | null
  new_value?: string | null
  reason?: string | null
  edited_by?: string | null
  edited_at: string
}

export type ProgressItemFilterOptions = {
  construction_units: string[]
  buildings: string[]
  floors: string[]
  disciplines: string[]
  system_names: string[]
  statuses: string[]
  floors_by_building: Record<string, string[]>
}
