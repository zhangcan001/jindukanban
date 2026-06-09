export type MaintenanceSummary = {
  database_url: string
  upload_dir: string
  export_dir: string
  project_count: number
  import_batch_count: number
  progress_item_count: number
  report_export_count: number
  backup_command: string
}

export type CleanupResponse = {
  dry_run: boolean
  cleanup_type?: string | null
  matched_count: number
  cleaned_count: number
  affected_count: number
  matched_ids: number[]
  skipped_count: number
  skipped_reasons: string[]
  log_written: boolean
  details: Array<Record<string, string | number | null | undefined>>
  message: string
}

export type RuntimeStatus = {
  app_version: string
  run_mode: string
  runtime_mode: string
  backend_status: string
  database_exists: boolean
  database_path: string
  upload_dir: string
  export_dir: string
  backup_dir: string
  project_count: number | string
  import_batch_count: number | string
  progress_item_count: number | string
  report_export_count: number | string
  last_backup_time: string
  backend_started_at: string
  portable_mode: boolean | string
  app_root: string
  data_dir: string
  log_dir: string
  frontend_dist_exists: boolean
  is_desktop_shell: boolean
  frontend_served_by_backend: boolean
  last_diagnose_time: string
  last_diagnose_log_path?: string | null
  is_release_package: boolean
  package_version?: string | null
}

export type AboutRuntimeInfo = {
  app_version: string
  runtime_mode: string
  run_mode: string
  database_path: string
  data_dir: string
  upload_dir: string
  export_dir: string
  backup_dir: string
  core_capabilities: string[]
  current_limits: string[]
  quick_actions: Array<{ label: string; path: string }>
}

export type DataHealth = {
  project_count: number | string
  archived_project_count: number | string
  active_project_count: number | string
  import_batch_count: number | string
  frozen_batch_count: number | string
  unfrozen_batch_count: number | string
  unpublished_batch_count: number | string
  draft_batch_count: number | string
  imported_unpublished_batch_count: number | string
  parsed_batch_count: number | string
  published_batch_count: number | string
  progress_item_count: number | string
  warning_record_count: number | string
  rectification_item_count: number | string
  report_export_count: number | string
  orphan_batch_count: number | string
  orphan_item_count: number | string
  missing_file_count: number | string
  database_size: number | string
  upload_dir_size: number | string
  export_dir_size: number | string
  backup_dir_size: number | string
  total_backup_count: number | string
  incomplete_backup_count: number | string
  temp_file_count: number | string
  maintenance_log_count: number | string
}

export type BackupRecord = {
  name: string
  backup_time: string
  has_database: boolean
  has_uploads: boolean
  has_exports: boolean
  has_backup_info: boolean
  size: number | string
  validation_status: string
  missing_items: string[]
  info_path?: string | null
  info_content?: string | null
  backup_path: string
}

export type BackupRestoreResponse = {
  restored: boolean
  message: string
  backup_name: string
  pre_restore_backup_name: string
  pre_restore_backup_path: string
  restored_database: boolean
  restored_uploads: boolean
  restored_exports: boolean
  restart_required: boolean
  log_written: boolean
}

export type MaintenanceLog = {
  id: number
  action: string
  target_type?: string | null
  target_id?: number | null
  summary: string
  detail?: string | null
  created_at: string
}

export type MaintenanceAiCallLog = {
  id: number
  project_id?: number | null
  batch_id?: number | null
  mode: string
  model?: string | null
  source: 'ai' | 'rule_fallback'
  success: boolean
  error_message?: string | null
  input_summary_length?: number | null
  output_length?: number | null
  duration_ms: number
  created_at: string
}
