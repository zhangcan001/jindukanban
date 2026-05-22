import type { FieldMapping } from './import'

export type ProjectTemplate = {
  id: number
  name: string
  code: string
  description?: string | null
  project_type?: string | null
  is_builtin: boolean
  is_active: boolean
  default_calculation_profile?: string | null
  default_warning_rules?: string | null
  default_field_aliases?: string | null
  default_dashboard_config?: string | null
  default_report_config?: string | null
  created_at: string
  updated_at: string
}

export type ProjectTemplatePayload = {
  name?: string | null
  description?: string | null
  project_type?: string | null
  is_active?: boolean | null
}

export type MappingTemplate = {
  id: number
  project_id?: number | null
  name: string
  description?: string | null
  project_type?: string | null
  is_global: boolean
  is_active: boolean
  last_used_at?: string | null
  use_count: number
  fields: FieldMapping[]
  created_at: string
  updated_at: string
}

export type MappingTemplatePayload = {
  name?: string | null
  description?: string | null
  project_type?: string | null
  is_active?: boolean | null
}
