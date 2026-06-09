from datetime import datetime
import logging
import os
from pathlib import Path
import shutil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import engine, get_db
from app.models.audit_log import AuditLog
from app.models.ai_call_log import AiCallLog
from app.models.baseline_plan import BaselinePlan
from app.models.calculation_profile import CalculationProfile
from app.models.import_batch import ImportBatch
from app.models.import_validation_issue import ImportValidationIssue
from app.models.mapping_field import MappingField
from app.models.mapping_template import MappingTemplate
from app.models.maintenance_log import MaintenanceLog
from app.models.progress_item import ProgressItem
from app.models.progress_item_edit_history import ProgressItemEditHistory
from app.models.progress_task import ProgressTask
from app.models.project import Project
from app.models.raw_import_row import RawImportRow
from app.models.rectification_item import RectificationItem
from app.models.report_export_record import ReportExportRecord
from app.models.warning_record import WarningRecord
from app.models.warning_rule import WarningRule
from app.schemas.ai import AiCallLogRead
from app.schemas.maintenance import (
    BackupRecord,
    BackupRestoreRequest,
    BackupRestoreResponse,
    AboutRuntimeInfo,
    CleanupRequest,
    CleanupResponse,
    DataHealthResponse,
    MaintenanceLogRead,
    MaintenanceSummary,
    RuntimeStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/maintenance", tags=["maintenance"])

TEST_PROJECT_KEYWORDS = ("测试", "test", "demo", "样例", "示例")
APP_VERSION = "v5.0-desktop-shell"
RESTORE_CONFIRM_TEXT = "我确认恢复备份"


@router.get("/summary", response_model=MaintenanceSummary)
def get_maintenance_summary(db: Session = Depends(get_db)) -> MaintenanceSummary:
    settings = get_settings()
    upload_dir = _ensure_directory(settings.upload_dir)
    export_dir = _ensure_directory(settings.export_dir)
    return MaintenanceSummary(
        database_url=_database_path(settings.database_url),
        upload_dir=str(upload_dir),
        export_dir=str(export_dir),
        project_count=_count(db, Project),
        import_batch_count=_count(db, ImportBatch),
        progress_item_count=_count(db, ProgressItem),
        report_export_count=_count(db, ReportExportRecord),
        backup_command="scripts\\backup.bat",
    )


@router.get("/runtime-status", response_model=RuntimeStatus)
def get_runtime_status(db: Session = Depends(get_db)) -> RuntimeStatus:
    settings = get_settings()
    app_root = _app_root()
    run_mode = _run_mode(app_root)
    database_path = _safe_database_path(settings.database_url)
    upload_dir = _safe_resolve(settings.upload_dir)
    export_dir = _safe_resolve(settings.export_dir)
    backup_dir = _safe_app_path(settings.backup_dir, app_root)
    log_dir = _safe_app_path("logs", app_root)
    data_dir = _safe_data_dir(database_path, app_root)
    return RuntimeStatus(
        app_version=APP_VERSION,
        run_mode=run_mode,
        runtime_mode=run_mode,
        backend_status="running",
        database_exists=Path(database_path).exists() if database_path != "-" else False,
        database_path=database_path,
        upload_dir=upload_dir,
        export_dir=export_dir,
        backup_dir=backup_dir,
        project_count=_safe_count(db, Project),
        import_batch_count=_safe_count(db, ImportBatch),
        progress_item_count=_safe_count(db, ProgressItem),
        report_export_count=_safe_count(db, ReportExportRecord),
        last_backup_time=_last_backup_time(Path(backup_dir)) if backup_dir != "-" else "-",
        backend_started_at=_backend_started_at(),
        portable_mode=_portable_mode(app_root),
        app_root=str(app_root) if app_root else "-",
        data_dir=data_dir,
        log_dir=log_dir,
        frontend_dist_exists=(app_root / "frontend_dist").exists() if app_root else False,
        is_desktop_shell=run_mode == "desktop-shell",
        frontend_served_by_backend=(app_root / "frontend_dist" / "index.html").exists() if app_root else False,
        last_diagnose_time=_last_diagnose_time(Path(log_dir)) if log_dir != "-" else "-",
        last_diagnose_log_path=_last_diagnose_log_path(Path(log_dir)) if log_dir != "-" else None,
        is_release_package=run_mode in {"portable", "installer-lite", "exe-launcher", "desktop-shell"},
        package_version=_package_version(app_root),
    )


@router.get("/about", response_model=AboutRuntimeInfo)
def get_about_runtime_info(db: Session = Depends(get_db)) -> AboutRuntimeInfo:
    status_info = get_runtime_status(db)
    return AboutRuntimeInfo(
        app_version=APP_VERSION,
        runtime_mode=status_info.run_mode,
        run_mode=status_info.run_mode,
        database_path=status_info.database_path,
        data_dir=status_info.data_dir,
        upload_dir=status_info.upload_dir,
        export_dir=status_info.export_dir,
        backup_dir=status_info.backup_dir,
        core_capabilities=[
            "Excel 单 Sheet / 多 Sheet 导入",
            "Dashboard V2 默认启用",
            "Dashboard V2：已启用",
            "预警记录",
            "整改闭环",
            "报表中心",
            "Word / PDF / Excel 导出",
            "本地备份恢复",
            "full_auto_check 自动验收",
            "full_auto_check：已支持",
            "portable 包",
            "示例数据与新手引导",
            "Windows 本地轻量安装包",
        ],
        current_limits=[
            "仅面向 Windows 本地单机使用",
            "不提供权限体系",
            "不支持 PostgreSQL / Docker",
            "不扩展 AI 能力",
            "Excel 导入和进度计算公式保持稳定",
        ],
        quick_actions=[
            {"label": "系统维护", "path": "/maintenance"},
            {"label": "帮助中心", "path": "/help"},
            {"label": "新手引导", "path": "/getting-started"},
            {"label": "项目管理", "path": "/projects"},
            {"label": "报表中心", "path": "/projects"},
        ],
    )


@router.get("/data-health", response_model=DataHealthResponse)
def get_data_health(db: Session = Depends(get_db)) -> DataHealthResponse:
    settings = get_settings()
    app_root = _app_root()
    database_path = _safe_database_path(settings.database_url)
    upload_dir = Path(_safe_resolve(settings.upload_dir))
    export_dir = Path(_safe_resolve(settings.export_dir))
    backup_dir_text = _safe_app_path(settings.backup_dir, app_root)
    backup_dir = Path(backup_dir_text) if backup_dir_text != "-" else None
    return DataHealthResponse(
        project_count=_safe_count(db, Project),
        archived_project_count=_safe_scalar(db, select(func.count()).select_from(Project).where(Project.is_archived.is_(True))),
        active_project_count=_safe_scalar(db, select(func.count()).select_from(Project).where(Project.is_archived.is_(False))),
        import_batch_count=_safe_count(db, ImportBatch),
        frozen_batch_count=_safe_scalar(db, select(func.count()).select_from(ImportBatch).where(ImportBatch.is_frozen.is_(True))),
        unfrozen_batch_count=_safe_scalar(db, select(func.count()).select_from(ImportBatch).where(ImportBatch.is_frozen.is_(False))),
        unpublished_batch_count=_safe_scalar(db, select(func.count()).select_from(ImportBatch).where(ImportBatch.status != "published")),
        draft_batch_count=_safe_scalar(db, select(func.count()).select_from(ImportBatch).where(ImportBatch.status == "draft")),
        imported_unpublished_batch_count=_safe_scalar(db, select(func.count()).select_from(ImportBatch).where(ImportBatch.status == "imported")),
        parsed_batch_count=_safe_scalar(db, select(func.count()).select_from(ImportBatch).where(ImportBatch.status == "parsed")),
        published_batch_count=_safe_scalar(db, select(func.count()).select_from(ImportBatch).where(ImportBatch.status == "published")),
        progress_item_count=_safe_count(db, ProgressItem),
        warning_record_count=_safe_count(db, WarningRecord),
        rectification_item_count=_safe_count(db, RectificationItem),
        report_export_count=_safe_count(db, ReportExportRecord),
        orphan_batch_count=_safe_orphan_batch_count(db),
        orphan_item_count=_safe_orphan_item_count(db),
        missing_file_count=_safe_missing_file_count(db),
        database_size=_file_size(database_path),
        upload_dir_size=_dir_size(upload_dir),
        export_dir_size=_dir_size(export_dir),
        backup_dir_size=_dir_size(backup_dir) if backup_dir else 0,
        total_backup_count=_backup_count(backup_dir),
        incomplete_backup_count=_incomplete_backup_count(backup_dir),
        temp_file_count=_temp_file_count(app_root),
        maintenance_log_count=_safe_count(db, MaintenanceLog),
    )


@router.get("/backups", response_model=list[BackupRecord])
def list_backup_records() -> list[BackupRecord]:
    settings = get_settings()
    backup_dir = Path(_safe_app_path(settings.backup_dir, _app_root()))
    if not backup_dir.exists():
        return []
    records: list[BackupRecord] = []
    for path in sorted((p for p in backup_dir.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True):
        info = _backup_record_info(path)
        records.append(
            BackupRecord(
                name=path.name,
                backup_time=_format_mtime(info["info_file"] if info["has_backup_info"] else path),
                has_database=info["has_database"],
                has_uploads=info["has_uploads"],
                has_exports=info["has_exports"],
                has_backup_info=info["has_backup_info"],
                size=_dir_size(path),
                validation_status="完整" if not info["missing_items"] else "不完整",
                missing_items=info["missing_items"],
                info_path=str(info["info_file"].resolve()) if info["has_backup_info"] else None,
                info_content=_read_text(info["info_file"]) if info["has_backup_info"] else None,
                backup_path=str(path.resolve()),
            )
        )
    return records


@router.get("/backups/{backup_name}", response_model=BackupRecord)
def get_backup_record(backup_name: str) -> BackupRecord:
    return _get_backup_record_or_404(backup_name)


@router.post("/backups/{backup_name}/validate", response_model=BackupRecord)
def validate_backup_record(backup_name: str) -> BackupRecord:
    return _get_backup_record_or_404(backup_name)


@router.post("/backups/{backup_name}/restore", response_model=BackupRestoreResponse)
def restore_backup_record(
    backup_name: str,
    payload: BackupRestoreRequest,
    db: Session = Depends(get_db),
) -> BackupRestoreResponse:
    if payload.confirm_text != RESTORE_CONFIRM_TEXT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="确认文字不匹配，已拒绝恢复。请输入“我确认恢复备份”。")

    record = _get_backup_record_or_404(backup_name)
    if record.validation_status != "完整":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="备份不完整，禁止恢复。请重新选择完整备份。")

    try:
        return _restore_backup(record, db)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"恢复失败：{_friendly_restore_error(exc)}") from exc


@router.get("/logs", response_model=list[MaintenanceLogRead])
def list_maintenance_logs(
    limit: int = Query(20, ge=1, le=100),
    action: str | None = None,
    db: Session = Depends(get_db),
) -> list[MaintenanceLogRead]:
    statement = select(MaintenanceLog)
    if action:
        statement = statement.where(MaintenanceLog.action == action)
    logs = list(db.scalars(statement.order_by(MaintenanceLog.created_at.desc(), MaintenanceLog.id.desc()).limit(limit)).all())
    return [
        MaintenanceLogRead(
            id=log.id,
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            summary=log.summary,
            detail=log.detail,
            created_at=log.created_at.isoformat(sep=" ", timespec="minutes"),
        )
        for log in logs
    ]


@router.get("/logs/{log_id}", response_model=MaintenanceLogRead)
def get_maintenance_log(log_id: int, db: Session = Depends(get_db)) -> MaintenanceLogRead:
    log = db.get(MaintenanceLog, log_id)
    if log is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance log not found")
    return MaintenanceLogRead(
        id=log.id,
        action=log.action,
        target_type=log.target_type,
        target_id=log.target_id,
        summary=log.summary,
        detail=log.detail,
        created_at=log.created_at.isoformat(sep=" ", timespec="minutes"),
    )


@router.get("/ai-logs", response_model=list[AiCallLogRead])
def list_ai_call_logs(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)) -> list[AiCallLog]:
    logs = list(db.scalars(select(AiCallLog).order_by(AiCallLog.created_at.desc(), AiCallLog.id.desc()).limit(limit)).all())
    return logs


@router.post("/safe-cleanup", response_model=CleanupResponse)
def safe_cleanup(payload: CleanupRequest, db: Session = Depends(get_db)) -> CleanupResponse:
    cleanup_type = payload.cleanup_type
    if cleanup_type == "unpublished_batches":
        return _cleanup_unpublished_batches(payload.dry_run, db)
    if cleanup_type == "empty_projects":
        return _cleanup_empty_projects(payload.dry_run, db)
    if cleanup_type == "temp_files":
        return _cleanup_temp_files(payload.dry_run, db)
    if cleanup_type == "orphan_export_records":
        return _cleanup_orphan_export_records(payload.dry_run, db)
    return CleanupResponse(dry_run=payload.dry_run, matched_count=0, cleaned_count=0, matched_ids=[], cleanup_type=cleanup_type, message="未知清理类型。")


@router.post("/cleanup-unpublished-batches", response_model=CleanupResponse)
def cleanup_unpublished_batches(dry_run: bool = Query(False), db: Session = Depends(get_db)) -> CleanupResponse:
    return _cleanup_unpublished_batches(dry_run, db)


def _cleanup_unpublished_batches(dry_run: bool, db: Session) -> CleanupResponse:
    batches = list(
        db.scalars(
            select(ImportBatch).where(
                ImportBatch.status != "published",
                ImportBatch.is_active.is_(True),
                ImportBatch.is_frozen.is_(False),
            )
        ).all()
    )
    batch_ids = [batch.id for batch in batches]
    skipped_count = _safe_scalar(db, select(func.count()).select_from(ImportBatch).where(ImportBatch.status != "published", ImportBatch.is_active.is_(True), ImportBatch.is_frozen.is_(True)))
    if not dry_run and batch_ids:
        _delete_batch_children(db, batch_ids)
        db.execute(update(ImportBatch).where(ImportBatch.id.in_(batch_ids)).values(is_active=False))
        _write_maintenance_log(db, "cleanup_unpublished_batches", "import_batch", None, f"清理未发布批次 {len(batch_ids)} 个", ",".join(map(str, batch_ids)))
        db.commit()
    return CleanupResponse(
        dry_run=dry_run,
        cleanup_type="unpublished_batches",
        matched_count=len(batch_ids),
        cleaned_count=0 if dry_run else len(batch_ids),
        matched_ids=batch_ids,
        skipped_count=skipped_count if isinstance(skipped_count, int) else 0,
        skipped_reasons=["冻结未发布批次已跳过"] if skipped_count else [],
        log_written=bool(not dry_run and batch_ids),
        details=[{"id": batch.id, "name": batch.file_name, "status": batch.status} for batch in batches],
        message="已扫描未发布批次；published 批次未受影响。",
    )


def _cleanup_empty_projects(dry_run: bool, db: Session) -> CleanupResponse:
    projects = list(db.scalars(select(Project)).all())
    matched_ids: list[int] = []
    details: list[dict[str, str | int | None]] = []
    skipped_reasons: list[str] = []
    for project in projects:
        if not _is_test_project(project.name):
            skipped_reasons.append(f"跳过正式项目：{project.name}")
            continue
        has_business_data = any(
            _safe_scalar(db, select(func.count()).select_from(model).where(model.project_id == project.id)) not in (0, "0")
            for model in (ImportBatch, ProgressTask, ProgressItem, WarningRecord, RectificationItem, ReportExportRecord)
        )
        if not has_business_data:
            matched_ids.append(project.id)
            details.append({"id": project.id, "name": project.name})
        else:
            skipped_reasons.append(f"跳过有业务数据项目：{project.name}")
    if not dry_run and matched_ids:
        db.execute(delete(Project).where(Project.id.in_(matched_ids)))
        _write_maintenance_log(db, "cleanup_empty_projects", "project", None, f"清理空测试项目 {len(matched_ids)} 个", ",".join(map(str, matched_ids)))
        db.commit()
    return CleanupResponse(
        dry_run=dry_run,
        cleanup_type="empty_projects",
        matched_count=len(matched_ids),
        cleaned_count=0 if dry_run else len(matched_ids),
        matched_ids=matched_ids,
        skipped_count=len(skipped_reasons),
        skipped_reasons=skipped_reasons[:20],
        log_written=bool(not dry_run and matched_ids),
        details=details,
        message="仅清理无业务数据的测试项目。",
    )


def _cleanup_temp_files(dry_run: bool, db: Session) -> CleanupResponse:
    temp_dirs = [_app_root() / ".runtime"] if _app_root() else []
    temp_files = []
    for temp_dir in temp_dirs:
        if temp_dir.exists():
            temp_files.extend(path for path in temp_dir.glob("*.tmp") if path.is_file())
    details = [{"path": str(path.resolve()), "name": path.name} for path in temp_files]
    if not dry_run:
        for path in temp_files:
            path.unlink(missing_ok=True)
        _write_maintenance_log(db, "cleanup_temp_files", "file", None, f"清理临时文件 {len(temp_files)} 个")
        db.commit()
    return CleanupResponse(
        dry_run=dry_run,
        cleanup_type="temp_files",
        matched_count=len(temp_files),
        cleaned_count=0 if dry_run else len(temp_files),
        matched_ids=[],
        log_written=bool(not dry_run),
        details=details,
        message="仅清理 .runtime 下的 .tmp 临时文件。",
    )


def _cleanup_orphan_export_records(dry_run: bool, db: Session) -> CleanupResponse:
    rows = list(db.scalars(select(ReportExportRecord)).all())
    matched = [row for row in rows if row.file_path and not Path(row.file_path).exists()]
    matched_ids = [row.id for row in matched]
    if not dry_run and matched_ids:
        db.execute(delete(ReportExportRecord).where(ReportExportRecord.id.in_(matched_ids)))
        _write_maintenance_log(db, "cleanup_orphan_exports", "report_export_record", None, f"清理孤立导出记录 {len(matched_ids)} 条", ",".join(map(str, matched_ids)))
        db.commit()
    return CleanupResponse(
        dry_run=dry_run,
        cleanup_type="orphan_export_records",
        matched_count=len(matched_ids),
        cleaned_count=0 if dry_run else len(matched_ids),
        matched_ids=matched_ids,
        log_written=bool(not dry_run and matched_ids),
        details=[{"id": row.id, "name": row.file_name, "path": row.file_path} for row in matched],
        message="仅清理文件已不存在的导出记录。",
    )


@router.post("/cleanup-test-projects", response_model=CleanupResponse)
def cleanup_test_projects(dry_run: bool = Query(True), db: Session = Depends(get_db)) -> CleanupResponse:
    projects = list(db.scalars(select(Project)).all())
    matched_ids = [project.id for project in projects if _is_test_project(project.name)]
    if not dry_run and matched_ids:
        _delete_projects(db, matched_ids)
        db.commit()
    return CleanupResponse(
        dry_run=dry_run,
        matched_count=len(matched_ids),
        cleaned_count=0 if dry_run else len(matched_ids),
        matched_ids=matched_ids,
        message="仅匹配名称包含测试/test/demo/样例/示例的项目。",
    )


def _count(db: Session, model: type) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def _ensure_directory(path_value: str) -> Path:
    path = Path(path_value).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _database_path(database_url: str) -> str:
    url = make_url(database_url)
    if url.drivername.startswith("sqlite") and url.database:
        return str(_repair_path(Path(url.database).resolve()))
    return database_url


def _safe_database_path(database_url: str) -> str:
    try:
        return _database_path(database_url)
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return "-"


def _safe_resolve(path_value: str) -> str:
    try:
        return str(_repair_path(Path(path_value).resolve()))
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return "-"


def _safe_app_path(path_value: str, app_root: Path | None) -> str:
    try:
        path = Path(path_value)
        if path.is_absolute():
            return str(_repair_path(path.resolve()))
        if path.parts and path.parts[0] == "..":
            return str(_repair_path(path.resolve()))
        root = app_root or Path.cwd().resolve()
        return str(_repair_path((root / path).resolve()))
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return "-"


def _app_root() -> Path | None:
    try:
        cwd = _repair_path(Path.cwd().resolve())
        return cwd.parent if cwd.name.lower() == "backend" else cwd
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return None


def _safe_data_dir(database_path: str, app_root: Path | None) -> str:
    if database_path != "-":
        try:
            return str(_repair_path(Path(database_path).resolve()).parent)
        except Exception as exc:
            logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
            pass
    if app_root:
        return str((app_root / "data").resolve())
    return "-"


def _repair_path(path: Path) -> Path:
    try:
        path_text = str(path)
        repaired_text = path_text.encode("latin1").decode("utf-8")
    except UnicodeError:
        return path
    if repaired_text == path_text:
        return path
    repaired = Path(repaired_text)
    try:
        if repaired.exists() or repaired.parent.exists():
            return repaired
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return path
    return path


def _portable_mode(app_root: Path | None) -> bool | str:
    try:
        if app_root is None:
            return "unknown"
        return (app_root / "frontend_dist").exists() and (app_root / "data").exists()
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return "unknown"


def _run_mode(app_root: Path | None) -> str:
    try:
        explicit_mode = os.environ.get("APP_RUN_MODE") or os.environ.get("APP_RUNTIME_MODE") or os.environ.get("FULL_AUTO_PACKAGE_MODE")
        if explicit_mode in {"source", "portable", "installer-lite", "exe-launcher", "desktop-shell"}:
            return explicit_mode
        if app_root is None:
            return "source"
        package_text = _package_info_text(app_root)
        if "包类型：Windows 独立桌面窗口版" in package_text:
            return "desktop-shell"
        if (app_root / "DESKTOP_SHELL").exists() or (app_root.parent / "DESKTOP_SHELL").exists():
            return "desktop-shell"
        if "包类型：Windows 可移植 EXE 启动包" in package_text:
            return "exe-launcher"
        if (app_root / "EXE_LAUNCHER").exists() or (app_root.parent / "EXE_LAUNCHER").exists():
            return "exe-launcher"
        if "包类型：Windows 本地轻量安装包" in package_text:
            return "installer-lite"
        if (app_root / "INSTALLER_LITE").exists() or (app_root.parent / "INSTALLER_LITE").exists():
            return "installer-lite"
        if app_root.name.lower().startswith("progress-dashboard-") and (app_root / "frontend_dist").exists():
            return "portable"
        if (app_root / "frontend_dist").exists() and (app_root / "data").exists():
            return "portable"
        return "source"
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return "source"


def _package_version(app_root: Path | None) -> str | None:
    if app_root is None:
        return APP_VERSION
    for line in _package_info_text(app_root).splitlines():
        if line.startswith("版本："):
            return line.split("：", 1)[1].strip() or APP_VERSION
    return APP_VERSION


def _package_info_text(app_root: Path) -> str:
    candidates = [app_root / "package_info.txt", app_root.parent / "package_info.txt"]
    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
            continue
    return ""


def _last_diagnose_time(log_dir: Path) -> str:
    latest = _latest_diagnose_log(log_dir)
    if latest is None:
        return "-"
    try:
        return _format_mtime(latest)
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return "-"


def _last_diagnose_log_path(log_dir: Path) -> str | None:
    latest = _latest_diagnose_log(log_dir)
    if latest is None:
        return None
    try:
        return str(latest.resolve())
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return None


def _latest_diagnose_log(log_dir: Path) -> Path | None:
    try:
        if not log_dir.exists():
            return None
        candidates = [path for path in log_dir.glob("diagnose_*.txt") if path.is_file()]
        if not candidates:
            return None
        return max(candidates, key=lambda path: path.stat().st_mtime)
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return None


def _safe_count(db: Session, model: type) -> int | str:
    try:
        return _count(db, model)
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return "-"


def _safe_scalar(db: Session, statement) -> int | str:
    try:
        return int(db.scalar(statement) or 0)
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return 0


def _file_size(path_value: str) -> int | str:
    try:
        if path_value == "-":
            return 0
        path = Path(path_value)
        return path.stat().st_size if path.exists() and path.is_file() else 0
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return 0


def _dir_size(path: Path | None) -> int | str:
    try:
        if path is None or not path.exists():
            return 0
        total = 0
        for child in path.rglob("*"):
            if child.is_file():
                total += child.stat().st_size
        return total
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return 0


def _safe_orphan_batch_count(db: Session) -> int | str:
    try:
        return int(
            db.scalar(
                select(func.count())
                .select_from(ImportBatch)
                .outerjoin(Project, ImportBatch.project_id == Project.id)
                .where(Project.id.is_(None))
            )
            or 0
        )
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return 0


def _safe_orphan_item_count(db: Session) -> int | str:
    try:
        return int(
            db.scalar(
                select(func.count())
                .select_from(ProgressItem)
                .outerjoin(ImportBatch, ProgressItem.batch_id == ImportBatch.id)
                .where(ImportBatch.id.is_(None))
            )
            or 0
        )
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return 0


def _safe_missing_file_count(db: Session) -> int | str:
    try:
        batches = list(db.scalars(select(ImportBatch).where(ImportBatch.file_path.is_not(None))).all())
        exports = list(db.scalars(select(ReportExportRecord).where(ReportExportRecord.file_path.is_not(None))).all())
        missing_batches = sum(1 for batch in batches if batch.file_path and not Path(batch.file_path).exists())
        missing_exports = sum(1 for record in exports if record.file_path and not Path(record.file_path).exists())
        return missing_batches + missing_exports
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return 0


def _backup_record_info(path: Path) -> dict:
    info_file = path / "backup_info.txt"
    has_database = any(path.glob("**/progress_dashboard.db"))
    has_uploads = (path / "uploads").exists() or (path / "backend" / "uploads").exists()
    has_exports = (path / "exports").exists() or (path / "reports").exists() or (path / "backend" / "reports").exists()
    has_backup_info = info_file.exists()
    missing_items = []
    if not has_database:
        missing_items.append("database")
    if not has_uploads:
        missing_items.append("uploads")
    if not has_exports:
        missing_items.append("exports")
    if not has_backup_info:
        missing_items.append("backup_info.txt")
    return {
        "info_file": info_file,
        "has_database": has_database,
        "has_uploads": has_uploads,
        "has_exports": has_exports,
        "has_backup_info": has_backup_info,
        "missing_items": missing_items,
    }


def _get_backup_record_or_404(backup_name: str) -> BackupRecord:
    settings = get_settings()
    backup_dir = Path(_safe_app_path(settings.backup_dir, _app_root()))
    backup_path = backup_dir / backup_name
    if not backup_path.exists() or not backup_path.is_dir():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到指定备份，请重新选择。")
    info = _backup_record_info(backup_path)
    return BackupRecord(
        name=backup_path.name,
        backup_time=_format_mtime(info["info_file"] if info["has_backup_info"] else backup_path),
        has_database=info["has_database"],
        has_uploads=info["has_uploads"],
        has_exports=info["has_exports"],
        has_backup_info=info["has_backup_info"],
        size=_dir_size(backup_path),
        validation_status="完整" if not info["missing_items"] else "不完整",
        missing_items=info["missing_items"],
        info_path=str(info["info_file"].resolve()) if info["has_backup_info"] else None,
        info_content=_read_text(info["info_file"]) if info["has_backup_info"] else None,
        backup_path=str(backup_path.resolve()),
    )


def _restore_backup(record: BackupRecord, db: Session) -> BackupRestoreResponse:
    settings = get_settings()
    app_root = _app_root()
    if app_root is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法定位应用根目录，恢复已取消。")

    backup_path = Path(record.backup_path)
    if not backup_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="备份目录不存在，无法恢复。")

    pre_restore_backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_pre_restore"
    pre_restore_backup_path = _create_current_backup(pre_restore_backup_name, app_root, settings)

    database_path = Path(_database_target_path(settings.database_url, app_root))
    upload_dir = Path(_restore_target_path(settings.upload_dir, app_root))
    export_dir = Path(_restore_target_path(settings.export_dir, app_root))

    restored_database = False
    restored_uploads = False
    restored_exports = False

    try:
        if record.has_database:
            source_db = next((path for path in backup_path.rglob("progress_dashboard.db") if path.is_file()), None)
            if source_db is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="备份中未找到数据库文件，无法恢复。")
            database_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_db, database_path)
            restored_database = True

        if record.has_uploads:
            source_uploads = _find_restore_source_dir(backup_path, ("uploads",))
            if source_uploads:
                _replace_directory(upload_dir, source_uploads)
                restored_uploads = True

        if record.has_exports:
            source_exports = _find_restore_source_dir(backup_path, ("exports", "reports", "backend/reports"))
            if source_exports:
                _replace_directory(export_dir, source_exports)
                restored_exports = True
    finally:
        engine.dispose()

    _write_maintenance_log(
        db,
        "restore_backup",
        "backup",
        None,
        f"恢复备份 {record.name}，恢复后建议重启系统。",
        f"恢复前自动备份：{pre_restore_backup_name}",
    )
    db.commit()

    return BackupRestoreResponse(
        restored=True,
        message="恢复完成，请重启系统后继续使用。",
        backup_name=record.name,
        pre_restore_backup_name=pre_restore_backup_name,
        pre_restore_backup_path=str(pre_restore_backup_path),
        restored_database=restored_database,
        restored_uploads=restored_uploads,
        restored_exports=restored_exports,
        restart_required=True,
        log_written=True,
    )


def _create_current_backup(backup_name: str, app_root: Path, settings) -> Path:
    backup_root = Path(_safe_app_path(settings.backup_dir, app_root))
    backup_root.mkdir(parents=True, exist_ok=True)
    target = backup_root / backup_name
    target.mkdir(parents=True, exist_ok=True)
    database_path = Path(_database_target_path(settings.database_url, app_root))
    upload_dir = Path(_restore_target_path(settings.upload_dir, app_root))
    export_dir = Path(_restore_target_path(settings.export_dir, app_root))
    if database_path.exists():
        shutil.copy2(database_path, target / "progress_dashboard.db")
    if upload_dir.exists():
        shutil.copytree(upload_dir, target / "uploads", dirs_exist_ok=True)
    if export_dir.exists():
        shutil.copytree(export_dir, target / _export_backup_dir_name(app_root), dirs_exist_ok=True)
    info = [
        f"备份时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"项目版本：{APP_VERSION}",
        f"数据库路径：{database_path}",
        f"上传目录：{upload_dir}",
        f"导出目录：{export_dir}",
        f"备份目录：{target}",
    ]
    (target / "backup_info.txt").write_text("\n".join(info), encoding="utf-8")
    return target


def _database_target_path(database_url: str, app_root: Path) -> str:
    url = make_url(database_url)
    if url.drivername.startswith("sqlite") and url.database:
        path = Path(url.database)
        return str(path if path.is_absolute() else (app_root / path).resolve())
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前仅支持 SQLite 备份恢复。")


def _restore_target_path(path_value: str, app_root: Path) -> str:
    path = Path(path_value)
    return str(path if path.is_absolute() else (app_root / path).resolve())


def _export_backup_dir_name(app_root: Path) -> str:
    return "exports" if (app_root / "frontend_dist").exists() else "reports"


def _find_restore_source_dir(backup_path: Path, candidates: tuple[str, ...]) -> Path | None:
    for candidate in candidates:
        direct = backup_path / candidate
        if direct.exists():
            return direct
        nested = backup_path / "backend" / candidate
        if nested.exists():
            return nested
    return None


def _replace_directory(target_dir: Path, source_dir: Path) -> None:
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, target_dir)


def _friendly_restore_error(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        return "未知错误"
    return message.splitlines()[0].replace("Traceback", "恢复异常")


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return None


def _backup_count(backup_dir: Path | None) -> int | str:
    try:
        if backup_dir is None or not backup_dir.exists():
            return 0
        return sum(1 for path in backup_dir.iterdir() if path.is_dir())
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return 0


def _incomplete_backup_count(backup_dir: Path | None) -> int | str:
    try:
        if backup_dir is None or not backup_dir.exists():
            return 0
        return sum(1 for path in backup_dir.iterdir() if path.is_dir() and _backup_record_info(path)["missing_items"])
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return 0


def _temp_file_count(app_root: Path | None) -> int | str:
    try:
        if app_root is None:
            return 0
        runtime = app_root / ".runtime"
        if not runtime.exists():
            return 0
        return sum(1 for path in runtime.glob("*.tmp") if path.is_file())
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return 0


def _last_backup_time(backup_dir: Path) -> str:
    try:
        if not backup_dir.exists():
            return "-"
        candidates = [path for path in backup_dir.iterdir() if path.is_dir() and path.name.startswith("backup_")]
        if not candidates:
            return "-"
        latest = max(candidates, key=lambda path: path.stat().st_mtime)
        info_file = latest / "backup_info.txt"
        if info_file.exists():
            return _format_mtime(info_file)
        return _format_mtime(latest)
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return "-"


def _format_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


def _backend_started_at() -> str:
    try:
        from app.main import BACKEND_STARTED_AT

        return BACKEND_STARTED_AT or "-"
    except Exception as exc:
        logger.debug("maintenance safe-getter swallowed: %s", exc, exc_info=True)
        return "-"


def _is_test_project(name: str) -> bool:
    normalized = name.lower()
    return any(keyword in normalized for keyword in TEST_PROJECT_KEYWORDS)


def _write_maintenance_log(
    db: Session,
    action: str,
    target_type: str,
    target_id: int | None,
    summary: str,
    detail: str | None = None,
) -> None:
    db.add(MaintenanceLog(action=action, target_type=target_type, target_id=target_id, summary=summary, detail=detail))


def _delete_batch_children(db: Session, batch_ids: list[int]) -> None:
    progress_item_ids = list(db.scalars(select(ProgressItem.id).where(ProgressItem.batch_id.in_(batch_ids))).all())
    if progress_item_ids:
        db.execute(delete(ProgressItemEditHistory).where(ProgressItemEditHistory.progress_item_id.in_(progress_item_ids)))
    db.execute(delete(WarningRecord).where(WarningRecord.batch_id.in_(batch_ids)))
    db.execute(delete(ReportExportRecord).where(ReportExportRecord.batch_id.in_(batch_ids)))
    db.execute(delete(ProgressItem).where(ProgressItem.batch_id.in_(batch_ids)))
    db.execute(delete(ImportValidationIssue).where(ImportValidationIssue.batch_id.in_(batch_ids)))
    db.execute(delete(RawImportRow).where(RawImportRow.batch_id.in_(batch_ids)))


def _delete_projects(db: Session, project_ids: list[int]) -> None:
    batch_ids = list(db.scalars(select(ImportBatch.id).where(ImportBatch.project_id.in_(project_ids))).all())
    if batch_ids:
        _delete_batch_children(db, batch_ids)
        db.execute(delete(ImportBatch).where(ImportBatch.id.in_(batch_ids)))

    template_ids = list(
        db.scalars(select(MappingTemplate.id).where(MappingTemplate.project_id.in_(project_ids))).all()
    )
    if template_ids:
        db.execute(delete(MappingField).where(MappingField.template_id.in_(template_ids)))
        db.execute(delete(MappingTemplate).where(MappingTemplate.id.in_(template_ids)))

    db.execute(delete(WarningRecord).where(WarningRecord.project_id.in_(project_ids)))
    db.execute(delete(WarningRule).where(WarningRule.project_id.in_(project_ids)))
    db.execute(delete(ProgressItem).where(ProgressItem.project_id.in_(project_ids)))
    db.execute(delete(ProgressTask).where(ProgressTask.project_id.in_(project_ids)))
    db.execute(delete(ReportExportRecord).where(ReportExportRecord.project_id.in_(project_ids)))
    db.execute(delete(BaselinePlan).where(BaselinePlan.project_id.in_(project_ids)))
    db.execute(delete(CalculationProfile).where(CalculationProfile.project_id.in_(project_ids)))
    db.execute(delete(AuditLog).where(AuditLog.project_id.in_(project_ids)))
    db.execute(delete(Project).where(Project.id.in_(project_ids)))









