from pydantic import BaseModel, model_validator


class MaintenanceSummary(BaseModel):
    database_url: str
    upload_dir: str
    export_dir: str
    project_count: int
    import_batch_count: int
    progress_item_count: int
    report_export_count: int
    backup_command: str


class RuntimeStatus(BaseModel):
    app_version: str
    run_mode: str = "source"
    runtime_mode: str = "source"
    backend_status: str
    database_exists: bool
    database_path: str
    upload_dir: str
    export_dir: str
    backup_dir: str
    project_count: int | str
    import_batch_count: int | str
    progress_item_count: int | str
    report_export_count: int | str
    last_backup_time: str
    backend_started_at: str
    portable_mode: bool | str
    app_root: str
    data_dir: str
    log_dir: str
    frontend_dist_exists: bool
    is_desktop_shell: bool = False
    frontend_served_by_backend: bool = False
    last_diagnose_time: str
    last_diagnose_log_path: str | None = None
    is_release_package: bool = False
    package_version: str | None = None


class AboutRuntimeInfo(BaseModel):
    app_version: str
    runtime_mode: str = "source"
    run_mode: str
    database_path: str
    data_dir: str
    upload_dir: str
    export_dir: str
    backup_dir: str
    core_capabilities: list[str]
    current_limits: list[str]
    quick_actions: list[dict[str, str]]


class CleanupResponse(BaseModel):
    dry_run: bool
    matched_count: int
    cleaned_count: int
    affected_count: int = 0
    matched_ids: list[int]
    message: str
    cleanup_type: str | None = None
    skipped_count: int = 0
    skipped_reasons: list[str] = []
    log_written: bool = False
    details: list[dict[str, str | int | None]] = []

    @model_validator(mode="after")
    def fill_affected_count(self) -> "CleanupResponse":
        self.affected_count = self.matched_count if self.dry_run else self.cleaned_count
        return self


class DataHealthResponse(BaseModel):
    project_count: int | str = 0
    archived_project_count: int | str = 0
    active_project_count: int | str = 0
    import_batch_count: int | str = 0
    frozen_batch_count: int | str = 0
    unfrozen_batch_count: int | str = 0
    unpublished_batch_count: int | str = 0
    published_batch_count: int | str = 0
    progress_item_count: int | str = 0
    warning_record_count: int | str = 0
    rectification_item_count: int | str = 0
    report_export_count: int | str = 0
    orphan_batch_count: int | str = 0
    orphan_item_count: int | str = 0
    missing_file_count: int | str = 0
    database_size: int | str = 0
    upload_dir_size: int | str = 0
    export_dir_size: int | str = 0
    backup_dir_size: int | str = 0
    total_backup_count: int | str = 0
    incomplete_backup_count: int | str = 0
    temp_file_count: int | str = 0
    maintenance_log_count: int | str = 0


class BackupRecord(BaseModel):
    name: str
    backup_time: str
    has_database: bool
    has_uploads: bool
    has_exports: bool
    has_backup_info: bool
    size: int | str = 0
    validation_status: str
    missing_items: list[str] = []
    info_path: str | None = None
    info_content: str | None = None
    backup_path: str


class BackupRestoreRequest(BaseModel):
    confirm_text: str


class BackupRestoreResponse(BaseModel):
    restored: bool
    message: str
    backup_name: str
    pre_restore_backup_name: str
    pre_restore_backup_path: str
    restored_database: bool
    restored_uploads: bool
    restored_exports: bool
    restart_required: bool = True
    log_written: bool = False


class MaintenanceLogRead(BaseModel):
    id: int
    action: str
    target_type: str | None = None
    target_id: int | None = None
    summary: str
    detail: str | None = None
    created_at: str


class CleanupRequest(BaseModel):
    cleanup_type: str
    dry_run: bool = True
