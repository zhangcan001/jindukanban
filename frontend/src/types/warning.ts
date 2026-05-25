export type WarningRule = {
  id: number
  project_id?: number | null
  name: string
  rule_type: string
  level: string
  threshold_value?: number | null
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export type WarningRulePayload = {
  name: string
  rule_type: string
  level: string
  threshold_value?: number | null
  is_enabled: boolean
}

export type WarningRecord = {
  id: number
  project_id: number
  batch_id?: number | null
  progress_item_id?: number | null
  task_id?: number | null
  rule_id?: number | null
  rule_name?: string | null
  level?: string | null
  level_label: string
  status: string
  status_label: string
  title?: string | null
  message?: string | null
  warning_message: string
  task_name: string
  discipline: string
  building: string
  floor: string
  system_name: string
  unit?: string | null
  actual_percent?: number | null
  planned_percent?: number | null
  progress_deviation?: number | null
  is_resolved: boolean
  created_at: string
  handled_at?: string | null
  remark?: string | null
  rectification_item_id?: number | null
  has_rectification?: boolean
}

export type WarningRunResponse = {
  batch_id: number
  generated_count: number
  records: WarningRecord[]
}

export type WarningRecordPage = {
  total: number
  records: WarningRecord[]
}

export type WarningRecordBatchResult = {
  updated_count: number
  skipped_ids: number[]
}

export type WarningResolutionType = 'handled' | 'ignored' | null

export type WarningFilters = {
  discipline?: string
  building?: string
  floor?: string
  level?: string
  status?: string
  keyword?: string
}

export type WarningFilterOptions = {
  disciplines: string[]
  buildings: string[]
  floors: string[]
  floors_by_building: Record<string, string[]>
}
