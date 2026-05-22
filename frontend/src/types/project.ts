export type Project = {
  id: number
  name: string
  project_type?: string | null
  owner_unit?: string | null
  supervision_unit?: string | null
  construction_unit?: string | null
  start_date?: string | null
  planned_finish_date?: string | null
  template_id?: number | null
  default_calculation_profile_id?: number | null
  default_calculation_method?: string | null
  default_baseline_plan_id?: number | null
  dashboard_config?: string | null
  report_config?: string | null
  ai_config?: string | null
  remark?: string | null
  is_archived: boolean
  archived_at?: string | null
  archive_remark?: string | null
  created_by?: string | null
  updated_by?: string | null
  created_at: string
  updated_at: string
}

export type ProjectPayload = Omit<Project, 'id' | 'created_at' | 'updated_at' | 'is_archived' | 'archived_at' | 'archive_remark'>
