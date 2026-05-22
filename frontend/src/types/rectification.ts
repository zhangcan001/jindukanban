export type RectificationStatus = 'open' | 'in_progress' | 'completed' | 'closed' | 'ignored'

export type RectificationItem = {
  id: number
  project_id: number
  batch_id?: number | null
  source_batch_label?: string | null
  source_baseline_plan_id?: number | null
  source_baseline_plan_name?: string | null
  progress_item_id?: number | null
  warning_record_id?: number | null
  source_type: string
  source_id?: number | null
  source_label: string
  discipline?: string | null
  building?: string | null
  floor?: string | null
  system_name?: string | null
  task_name?: string | null
  issue_description?: string | null
  delay_level?: string | null
  delay_level_label: string
  actual_percent?: number | null
  planned_percent?: number | null
  progress_deviation?: number | null
  responsible_person?: string | null
  responsible_unit?: string | null
  planned_finish_date?: string | null
  status: RectificationStatus
  status_label: string
  review_result?: string | null
  remark?: string | null
  is_overdue: boolean
  created_at: string
  updated_at: string
  closed_at?: string | null
}

export type RectificationListResponse = {
  items: RectificationItem[]
  total: number
  page: number
  page_size: number
}

export type RectificationSummary = {
  total: number
  open: number
  in_progress: number
  completed: number
  closed: number
  ignored: number
  overdue: number
  serious: number
  new_this_week: number
  closed_this_week: number
}

export type RectificationActionLog = {
  id: number
  rectification_item_id: number
  project_id: number
  action: string
  action_label: string
  operator: string
  from_status?: string | null
  from_status_label?: string | null
  to_status?: string | null
  to_status_label?: string | null
  content?: string | null
  created_at: string
}

export type RectificationFilters = {
  page?: number
  page_size?: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
  status?: string
  delay_level?: string
  discipline?: string
  building?: string
  floor?: string
  responsible_person?: string
  responsible_unit?: string
  overdue?: boolean | null
  source_type?: string
  keyword?: string
  scope?: string | null
  data_date?: string | null
  import_group_id?: string | null
  batch_ids?: string | null
  batch_id?: number | null
  baseline_plan_id?: number | null
  calculation_method?: string | null
}

export type RectificationFilterOptions = {
  disciplines: string[]
  buildings: string[]
  floors: string[]
  responsible_persons: string[]
  responsible_units: string[]
  delay_levels: string[]
  statuses: string[]
  source_types: string[]
  floors_by_building: Record<string, string[]>
}
