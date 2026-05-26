export type ImportBatch = {
  id: number
  project_id: number
  file_name: string
  file_path?: string | null
  sheet_name?: string | null
  import_group_id?: string | null
  import_group_name?: string | null
  is_multi_sheet: boolean
  group_sheet_count: number
  is_frozen: boolean
  frozen_at?: string | null
  freeze_remark?: string | null
  data_date?: string | null
  header_row_index?: number | null
  data_start_row_index?: number | null
  multi_header: boolean
  header_end_row_index?: number | null
  row_count: number
  imported_count: number
  skipped_count: number
  warning_count: number
  error_count: number
  data_quality_score?: number | null
  field_completeness?: number | null
  task_match_rate?: number | null
  valid_row_rate?: number | null
  plan_field_completeness?: number | null
  unit_consistency?: number | null
  status: string
  calculation_profile_id?: number | null
  baseline_plan_id?: number | null
  baseline_plan_name?: string | null
  created_at: string
  updated_at: string
}

export type ImportUploadResponse = {
  batch: ImportBatch
  sheets: string[]
}

export type ImportParseRequest = {
  sheet_name: string
  data_date?: string | null
  header_row_index?: number | null
  data_start_row_index?: number | null
  multi_header: boolean
  header_end_row_index?: number | null
}

export type ParsedColumn = {
  name: string
  field_type: string
  recommended_field?: string | null
  is_dimension: boolean
  is_metric: boolean
  save_to_extra: boolean
  match_type?: string | null
  confidence?: string | null
  reason?: string | null
  field_role?: string | null
  is_required?: boolean
  affects_statistics?: boolean
  affects_delay?: boolean
  alias_source?: 'rule' | 'history-exact' | 'history-fuzzy' | 'ai_fallback' | null
  alias_confidence?: number | null
  needs_review?: boolean
  sample_values?: string[]
}

export type HeaderRecommendation = {
  header_row_index?: number | null
  data_start_row_index?: number | null
  confidence: string
}

export type FieldMapping = {
  excel_column_name: string
  recommended_field?: string | null
  system_field_name?: string | null
  field_type: string
  is_dimension: boolean
  is_metric: boolean
  is_required: boolean
  save_to_extra: boolean
  sort_order: number
  match_type?: string | null
  confidence?: string | null
  reason?: string | null
  field_role?: string | null
  affects_statistics?: boolean
  affects_delay?: boolean
  needs_review?: boolean
  sample_values?: string[]
}

export type FieldDiagnostics = {
  field_mapping_quality: {
    recognized_count: number
    total_count: number
    score: number
    label: string
  }
  recognized_fields: Array<{
    excel_column_name: string
    system_field_name?: string | null
    recommended_field?: string | null
    field_type: string
    match_type: string
    confidence: string
    reason: string
    field_role: string
    is_required: boolean
    affects_statistics: boolean
    affects_delay: boolean
  }>
  missing_core_fields: string[]
  field_impacts: Array<{ field: string; field_label: string; impact: string }>
  available_calculation_methods: Array<{
    code: string
    name: string
    available: boolean
    recommended: boolean
    reason: string
    warning?: string | null
    not_recommended_reason?: string | null
  }>
  recommended_calculation_method: string
  recommended_calculation_method_name: string
  recommended_reason: string
  unit_diagnostics: {
    unit_field_exists: boolean
    unit_list: string[]
    is_mixed: boolean
    message?: string | null
  }
  weight_diagnostics: {
    weight_field_exists: boolean
    weight_total?: number | null
    valid_weight_task_count: number
    missing_weight_task_count: number
  }
  field_completeness_summary: {
    quantity_field_complete_rate: number
    plan_date_complete_rate: number
    actual_percent_complete_rate: number
  }
  dashboard_capabilities: Record<string, { available: boolean; reason: string }>
}

export type MatchedTemplate = {
  id: number
  name: string
  description?: string | null
  match_score: number
  hit_field_count: number
  missing_field_count: number
  possible_mismatch_fields: string[]
  field_structure?: Record<string, unknown> | null
  fields: FieldMapping[]
  is_exact_match: boolean
  match_reason?: string | null
}

export type MappingValidationIssue = {
  level: string
  code: string
  message: string
  excel_column_name?: string | null
  system_field_name?: string | null
}

export type ImportParseResponse = {
  batch: ImportBatch
  columns: ParsedColumn[]
  preview_rows: Record<string, unknown>[]
  matched_templates: MatchedTemplate[]
  header_recommendation?: HeaderRecommendation | null
  field_diagnostics?: FieldDiagnostics | null
}

export type MappingValidationResponse = {
  valid: boolean
  issues: MappingValidationIssue[]
}

export type ImportValidationIssue = {
  row_index?: number | null
  column_name?: string | null
  level: string
  code?: string | null
  message: string
}

export type AbnormalPreviewExample = {
  row_index?: number | null
  column_name?: string | null
  raw_value?: unknown
  message: string
  level: string
  code?: string | null
}

export type AbnormalPreviewGroup = {
  type: string
  level: string
  count: number
  examples: AbnormalPreviewExample[]
}

export type DataQualityScore = {
  data_quality_score: number
  field_completeness: number
  task_match_rate: number
  valid_row_rate: number
  plan_field_completeness: number
  unit_consistency: number
}

export type ValidationIssueCodeCount = {
  code: string
  level: string
  count: number
}

export type ImportStrategy = 'new_batch' | 'replace_same_date' | 'overwrite_current'

export type ImportConfirmRequest = {
  template_name?: string | null
  save_as_template: boolean
  data_date?: string | null
  calculation_profile_id?: number | null
  baseline_plan_id?: number | null
  mapping_template_id?: number | null
  import_strategy: ImportStrategy
  field_mappings: FieldMapping[]
}

export type ImportConfirmResponse = {
  valid: boolean
  status: string
  imported_count: number
  skipped_count: number
  task_created_count: number
  task_matched_count: number
  raw_row_count: number
  template_id?: number | null
  warning_count: number
  error_count: number
  data_quality: DataQualityScore
  issues: ImportValidationIssue[]
  issue_code_counts: ValidationIssueCodeCount[]
}

export type ImportPublishResponse = {
  id: number
  project_id: number
  status: string
  is_active: boolean
  imported_count: number
  warning_count: number
  error_count: number
  data_quality_score?: number | null
  published_by?: string | null
  published_at: string
}

export type MultiSheetPublishResult = {
  batch_id: number
  sheet_name?: string | null
  status: string
  published: boolean
  error?: string | null
  result?: ImportPublishResponse | null
}

export type MultiSheetPublishResponse = {
  total_count: number
  published_count: number
  failed_publish_count: number
  results: MultiSheetPublishResult[]
}

export type ImportValidationResponse = {
  valid: boolean
  warning_count: number
  error_count: number
  data_quality: DataQualityScore
  issues: ImportValidationIssue[]
  issue_code_counts: ValidationIssueCodeCount[]
  abnormal_preview: AbnormalPreviewGroup[]
  normalized_preview_rows: Record<string, unknown>[]
}

export type MultiSheetParseRequest = {
  project_id: number
  sheet_names: string[]
  header_row_index?: number | null
  data_start_row_index?: number | null
  data_date?: string | null
  baseline_plan_id?: number | null
  multi_header: boolean
  header_end_row_index?: number | null
}

export type MultiSheetParseResult = {
  sheet_name: string
  status: string
  batch_id?: number | null
  columns: ParsedColumn[]
  preview_rows: Record<string, unknown>[]
  suggested_mappings: MatchedTemplate[]
  warning?: string | null
  error?: string | null
  header_row_index?: number | null
  data_start_row_index?: number | null
  header_recommendation?: HeaderRecommendation | null
  row_count: number
}

export type MultiSheetParseResponse = {
  import_group_id?: string | null
  import_group_name?: string | null
  file_id: number
  project_id: number
  total_sheets: number
  success_count: number
  failed_count: number
  results: MultiSheetParseResult[]
}

export type MultiSheetValidationSheetRequest = {
  batch_id: number
  sheet_name: string
  mappings: FieldMapping[]
  header_row_index?: number | null
  data_start_row_index?: number | null
}

export type MultiSheetValidationResult = {
  sheet_name: string
  batch_id: number
  valid: boolean
  warning_count: number
  error_count: number
  skipped_count: number
  data_quality_score?: number | null
  issues: ImportValidationIssue[]
  abnormal_preview: AbnormalPreviewGroup[]
  error?: string | null
}

export type MultiSheetValidationResponse = {
  total_sheets: number
  success_count: number
  failed_count: number
  results: MultiSheetValidationResult[]
}

export type MultiSheetConfirmSheetRequest = {
  batch_id: number
  sheet_name: string
  mappings: FieldMapping[]
  import_strategy: ImportStrategy
  save_template: boolean
  template_name?: string | null
  mapping_template_id?: number | null
}

export type MultiSheetConfirmBatchResult = {
  sheet_name: string
  batch_id?: number | null
  imported_count: number
  skipped_count: number
  warning_count: number
  error_count: number
  status: string
  error?: string | null
}

export type MultiSheetConfirmRequest = {
  project_id: number
  data_date?: string | null
  baseline_plan_id?: number | null
  calculation_profile_id?: number | null
  sheets: MultiSheetConfirmSheetRequest[]
}

export type MultiSheetConfirmResponse = {
  total_sheets: number
  success_count: number
  failed_count: number
  batches: MultiSheetConfirmBatchResult[]
}
