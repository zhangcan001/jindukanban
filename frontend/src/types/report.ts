export type ReportExportRecord = {
  id: number
  project_id: number
  batch_id?: number | null
  report_type: string
  file_name?: string | null
  file_path?: string | null
  data_date?: string | null
  exported_by?: string | null
  exported_at: string
}

export type ReportType = 'dashboard_excel' | 'weekly_word' | 'weekly_pdf' | 'delay_rectification_excel' | 'rectification_tracking' | 'maintenance_report'

export type ReportConfig = {
  include_advanced_chart_analysis: boolean
  use_ai_weekly_text: boolean
  weekly_delayed_item_limit: number
  weekly_matrix_summary_limit: number
  show_data_quality_section: boolean
  show_rectification_summary: boolean
  default_export_format: 'xlsx' | 'docx'
  file_name_include_project_name: boolean
  file_name_include_data_date: boolean
}

export type ReportPreview = {
  report_type: string
  title: string
  items: Array<{ label: string; value: string | number | boolean | string[] | null }>
}

export type ReportHistoryFilters = {
  reportType?: string | null
  projectName?: string | null
  dateFrom?: string | null
  dateTo?: string | null
  keyword?: string | null
}

export type DelayRectificationFilters = {
  discipline?: string | null
  building?: string | null
  floor?: string | null
  delayLevel?: string | null
  calculationMethod?: string | null
}
