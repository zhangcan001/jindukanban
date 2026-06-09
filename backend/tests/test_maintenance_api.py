from pathlib import Path

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.import_batch import ImportBatch
from app.models.maintenance_log import MaintenanceLog
from app.models.progress_item import ProgressItem
from app.models.project import Project
from app.models.rectification_item import RectificationItem
from app.models.report_export_record import ReportExportRecord


def expected_runtime_mode() -> str:
    explicit_mode = (
        __import__("os").environ.get("APP_RUN_MODE")
        or __import__("os").environ.get("APP_RUNTIME_MODE")
        or __import__("os").environ.get("FULL_AUTO_PACKAGE_MODE")
    )
    if explicit_mode in {"source", "portable", "installer-lite", "exe-launcher", "desktop-shell"}:
        return explicit_mode

    cwd = Path.cwd().resolve()
    parts = {part.lower() for part in cwd.parts}
    path_text = str(cwd)
    package_info_candidates = [cwd / "package_info.txt", cwd.parent / "package_info.txt"]
    package_info_text = ""
    for candidate in package_info_candidates:
        if candidate.exists():
            package_info_text = candidate.read_text(encoding="utf-8", errors="replace")
            break

    if "包类型：Windows 独立桌面窗口版" in package_info_text or (cwd / "DESKTOP_SHELL").exists() or (cwd.parent / "DESKTOP_SHELL").exists():
        return "desktop-shell"
    if "包类型：Windows 可移植 EXE 启动包" in package_info_text or (cwd / "EXE_LAUNCHER").exists() or (cwd.parent / "EXE_LAUNCHER").exists():
        return "exe-launcher"
    if "包类型：Windows 本地轻量安装包" in package_info_text or (cwd / "INSTALLER_LITE").exists() or (cwd.parent / "INSTALLER_LITE").exists():
        return "installer-lite"
    if "release" in parts and "工程进度管理系统-" in path_text:
        return "installer-lite"
    if "包类型：portable" in package_info_text.lower() or "progress-dashboard-" in cwd.name.lower():
        return "portable"
    if "release" in parts and any(part.lower().startswith("progress-dashboard-") for part in cwd.parts):
        return "portable"
    return "source"


def test_maintenance_summary_returns_counts_and_paths() -> None:
    db = SessionLocal()
    try:
        project = Project(name="正式项目")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="a.csv", status="published")
        db.add(batch)
        db.flush()
        db.add(ProgressItem(project_id=project.id, batch_id=batch.id, task_name="桥架安装"))
        db.add(ReportExportRecord(project_id=project.id, batch_id=batch.id, report_type="overview"))
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/api/maintenance/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["database_url"].endswith("test_progress_dashboard.db")
    assert data["upload_dir"]
    assert data["export_dir"]
    assert data["project_count"] == 1
    assert data["import_batch_count"] == 1
    assert data["progress_item_count"] == 1
    assert data["report_export_count"] == 1
    assert data["backup_command"] == "scripts\\backup.bat"


def test_runtime_status_returns_running_state_counts_and_paths() -> None:
    db = SessionLocal()
    try:
        project = Project(name="运行状态项目")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="a.csv", status="published")
        db.add(batch)
        db.add(ReportExportRecord(project_id=project.id, batch_id=batch.id, report_type="overview"))
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/api/maintenance/runtime-status")

    assert response.status_code == 200
    data = response.json()
    expected_mode = expected_runtime_mode()
    assert data["app_version"] == "v5.0-desktop-shell"
    assert data["run_mode"] == expected_mode
    assert data["runtime_mode"] == expected_mode
    assert data["backend_status"] == "running"
    assert data["database_exists"] is True
    assert data["database_path"].endswith("test_progress_dashboard.db")
    assert data["upload_dir"]
    assert data["export_dir"]
    assert data["backup_dir"]
    assert data["project_count"] == 1
    assert data["import_batch_count"] == 1
    assert data["progress_item_count"] == 0
    assert data["report_export_count"] == 1
    assert data["last_backup_time"]
    assert data["backend_started_at"]
    assert "portable_mode" in data
    assert data["app_root"]
    assert data["data_dir"]
    assert data["log_dir"]
    assert data["backup_dir"]
    assert "frontend_dist_exists" in data
    assert "is_desktop_shell" in data
    assert "frontend_served_by_backend" in data
    assert data["last_diagnose_time"]
    assert "last_diagnose_log_path" in data
    assert data["is_release_package"] is (expected_mode != "source")
    assert data["package_version"]


def test_about_runtime_info_returns_desktop_package_details() -> None:
    with TestClient(app) as client:
        response = client.get("/api/maintenance/about")

    assert response.status_code == 200
    data = response.json()
    expected_mode = expected_runtime_mode()
    assert data["app_version"] == "v5.0-desktop-shell"
    assert data["runtime_mode"] == expected_mode
    assert data["run_mode"] == expected_mode
    assert data["database_path"]
    assert data["data_dir"]
    assert data["upload_dir"]
    assert data["export_dir"]
    assert data["backup_dir"]
    assert "Word / PDF / Excel 导出" in data["core_capabilities"]
    assert "Dashboard V2：已启用" in data["core_capabilities"]
    assert "full_auto_check：已支持" in data["core_capabilities"]
    assert "portable 包" in data["core_capabilities"]
    assert data["current_limits"]
    assert any(item["path"] == "/help" for item in data["quick_actions"])


def test_runtime_status_tolerates_unavailable_portable_paths(monkeypatch) -> None:
    from app.routers import maintenance

    monkeypatch.setattr(maintenance, "_safe_app_path", lambda path_value, app_root: "-")

    with TestClient(app) as client:
        response = client.get("/api/maintenance/runtime-status")

    assert response.status_code == 200
    data = response.json()
    assert data["backup_dir"] == "-"
    assert data["log_dir"] == "-"
    assert data["last_backup_time"] == "-"
    assert data["last_diagnose_time"] == "-"
    assert data["last_diagnose_log_path"] is None


def test_runtime_status_without_backups_directory_does_not_fail(tmp_path, monkeypatch) -> None:
    from app.routers import maintenance

    missing_backups = tmp_path / "missing-backups"
    logs = tmp_path / "logs"
    logs.mkdir()

    def fake_safe_app_path(path_value, app_root):
        return str(logs if path_value == "logs" else missing_backups)

    monkeypatch.setattr(maintenance, "_safe_app_path", fake_safe_app_path)

    with TestClient(app) as client:
        response = client.get("/api/maintenance/runtime-status")

    assert response.status_code == 200
    data = response.json()
    assert data["last_backup_time"] == "-"
    assert data["last_diagnose_time"] == "-"


def test_project_archive_restore_hides_from_default_list_and_keeps_data() -> None:
    with TestClient(app) as client:
        created = client.post("/api/projects", json={"name": "归档项目测试"}).json()
        project_id = created["id"]

        db = SessionLocal()
        try:
            batch = ImportBatch(project_id=project_id, file_name="history.csv", status="published")
            db.add(batch)
            db.flush()
            db.add(ProgressItem(project_id=project_id, batch_id=batch.id, task_name="历史任务"))
            db.commit()
        finally:
            db.close()

        archived = client.post(f"/api/projects/{project_id}/archive", json={"archive_remark": "阶段完成"})
        default_list = client.get("/api/projects")
        archived_list = client.get("/api/projects?include_archived=true")
        upload_blocked = client.post(f"/api/projects/{project_id}/imports/upload", files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")})
        baseline_blocked = client.post(f"/api/projects/{project_id}/baseline-plans", json={"name": "归档后基线"})
        rectification_blocked = client.post(
            f"/api/projects/{project_id}/rectifications",
            json={"task_name": "归档后整改", "issue_description": "不应创建", "status": "open"},
        )
        report_allowed = client.get(f"/api/projects/{project_id}/reports/dashboard-export")
        restored = client.post(f"/api/projects/{project_id}/restore")

    assert archived.status_code == 200
    assert archived.json()["is_archived"] is True
    assert project_id not in {project["id"] for project in default_list.json()}
    assert project_id in {project["id"] for project in archived_list.json()}
    assert upload_blocked.status_code == 400
    assert baseline_blocked.status_code == 400
    assert rectification_blocked.status_code == 400
    assert report_allowed.status_code == 200
    assert restored.status_code == 200
    assert restored.json()["is_archived"] is False

    db = SessionLocal()
    try:
        assert db.query(ProgressItem).filter(ProgressItem.project_id == project_id).count() == 1
        assert db.query(MaintenanceLog).filter(MaintenanceLog.target_id == project_id).count() >= 2
    finally:
        db.close()


def test_cleanup_unpublished_batches_does_not_affect_published_batch() -> None:
    db = SessionLocal()
    try:
        project = Project(name="正式项目")
        db.add(project)
        db.flush()
        published = ImportBatch(project_id=project.id, file_name="published.csv", status="published")
        draft = ImportBatch(project_id=project.id, file_name="draft.csv", status="draft")
        db.add_all([published, draft])
        db.flush()
        db.add_all(
            [
                ProgressItem(project_id=project.id, batch_id=published.id, task_name="已发布任务"),
                ProgressItem(project_id=project.id, batch_id=draft.id, task_name="草稿任务"),
            ]
        )
        db.commit()
        published_id = published.id
        draft_id = draft.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.post("/api/maintenance/cleanup-unpublished-batches")

    assert response.status_code == 200
    data = response.json()
    assert data["matched_ids"] == [draft_id]
    assert data["cleaned_count"] == 1

    db = SessionLocal()
    try:
        assert db.get(ImportBatch, published_id).is_active is True
        assert db.get(ImportBatch, draft_id).is_active is False
        assert db.query(ProgressItem).filter(ProgressItem.batch_id == published_id).count() == 1
        assert db.query(ProgressItem).filter(ProgressItem.batch_id == draft_id).count() == 0
    finally:
        db.close()


def test_cleanup_test_projects_only_matches_test_like_names() -> None:
    db = SessionLocal()
    try:
        normal = Project(name="机场正式项目")
        demo = Project(name="Demo 样例项目")
        test_project = Project(name="测试项目")
        db.add_all([normal, demo, test_project])
        db.commit()
        normal_id = normal.id
        demo_id = demo.id
        test_id = test_project.id
    finally:
        db.close()

    with TestClient(app) as client:
        dry_run = client.post("/api/maintenance/cleanup-test-projects?dry_run=true")
        response = client.post("/api/maintenance/cleanup-test-projects?dry_run=false")
        remaining = client.get("/api/projects")

    assert dry_run.status_code == 200
    assert sorted(dry_run.json()["matched_ids"]) == sorted([demo_id, test_id])
    assert response.status_code == 200
    assert sorted(response.json()["matched_ids"]) == sorted([demo_id, test_id])
    remaining_ids = {project["id"] for project in remaining.json()}
    assert normal_id in remaining_ids
    assert demo_id not in remaining_ids
    assert test_id not in remaining_ids


def test_data_health_backup_records_safe_cleanup_and_logs(tmp_path, monkeypatch) -> None:
    from app.routers import maintenance

    backup_root = tmp_path / "backups"
    backup = backup_root / "backup_20260517_120000"
    incomplete = backup_root / "backup_20260517_130000"
    (backup / "uploads").mkdir(parents=True)
    (backup / "exports").mkdir()
    incomplete.mkdir(parents=True)
    (backup / "progress_dashboard.db").write_text("db", encoding="utf-8")
    (backup / "backup_info.txt").write_text("info", encoding="utf-8")

    monkeypatch.setattr(maintenance, "_safe_app_path", lambda path_value, app_root: str(backup_root) if path_value == "backups" else str(tmp_path / path_value))

    db = SessionLocal()
    try:
        project = Project(name="维护测试空项目")
        db.add(project)
        db.flush()
        published = ImportBatch(project_id=project.id, file_name="published.csv", status="published", is_frozen=True)
        draft = ImportBatch(project_id=project.id, file_name="draft.csv", status="draft")
        parsed = ImportBatch(project_id=project.id, file_name="parsed.csv", status="parsed")
        imported = ImportBatch(project_id=project.id, file_name="imported.csv", status="imported")
        db.add_all([published, draft, parsed, imported])
        db.commit()
        draft_id = draft.id
        parsed_id = parsed.id
        imported_id = imported.id
        published_id = published.id
    finally:
        db.close()

    with TestClient(app) as client:
        health = client.get("/api/maintenance/data-health")
        backups = client.get("/api/maintenance/backups")
        preview = client.post("/api/maintenance/safe-cleanup", json={"cleanup_type": "unpublished_batches", "dry_run": True})
        cleanup = client.post("/api/maintenance/safe-cleanup", json={"cleanup_type": "unpublished_batches", "dry_run": False})
        logs = client.get("/api/maintenance/logs")

    assert health.status_code == 200
    health_data = health.json()
    assert health_data["frozen_batch_count"] == 1
    assert health_data["published_batch_count"] == 1
    assert health_data["unpublished_batch_count"] == 3
    assert health_data["draft_batch_count"] == 1
    assert health_data["parsed_batch_count"] == 1
    assert health_data["imported_unpublished_batch_count"] == 1
    assert health_data["total_backup_count"] == 2
    assert health_data["incomplete_backup_count"] == 1
    assert "maintenance_log_count" in health_data
    assert backups.status_code == 200
    records = backups.json()
    complete_record = next(record for record in records if record["name"] == "backup_20260517_120000")
    incomplete_record = next(record for record in records if record["name"] == "backup_20260517_130000")
    assert complete_record["has_database"] is True
    assert complete_record["has_uploads"] is True
    assert complete_record["has_exports"] is True
    assert complete_record["has_backup_info"] is True
    assert complete_record["validation_status"] == "完整"
    assert complete_record["info_content"] == "info"
    assert incomplete_record["validation_status"] == "不完整"
    assert "database" in incomplete_record["missing_items"]
    preview_data = preview.json()
    assert set(preview_data["matched_ids"]) == {draft_id, parsed_id, imported_id}
    assert preview_data["affected_count"] == 3
    assert {detail["id"] for detail in preview_data["details"]} == {draft_id, parsed_id, imported_id}
    assert preview_data["cleanup_type"] == "unpublished_batches"
    assert cleanup.json()["cleaned_count"] == 3
    assert cleanup.json()["affected_count"] == 3
    assert cleanup.json()["log_written"] is True

    db = SessionLocal()
    try:
        assert db.get(ImportBatch, published_id).is_active is True
        assert db.get(ImportBatch, draft_id).is_active is False
        assert db.get(ImportBatch, parsed_id).is_active is False
        assert db.get(ImportBatch, imported_id).is_active is False
        assert db.query(MaintenanceLog).filter(MaintenanceLog.action == "cleanup_unpublished_batches").count() == 1
    finally:
        db.close()

    assert logs.status_code == 200
    cleanup_logs = [log for log in logs.json() if log["action"] == "cleanup_unpublished_batches"]
    assert cleanup_logs
    with TestClient(app) as client:
        detail = client.get(f"/api/maintenance/logs/{cleanup_logs[0]['id']}")
        filtered = client.get("/api/maintenance/logs?action=cleanup_unpublished_batches")
    assert detail.status_code == 200
    assert detail.json()["action"] == "cleanup_unpublished_batches"
    assert filtered.status_code == 200
    assert all(log["action"] == "cleanup_unpublished_batches" for log in filtered.json())


def test_backup_detail_validate_and_restore_safety(tmp_path, monkeypatch) -> None:
    from app.routers import maintenance

    app_root = tmp_path / "app"
    backup_root = app_root / "backups"
    uploads = app_root / "uploads"
    reports = app_root / "reports"
    db_path = app_root / "test_progress_dashboard.db"
    target_backup = backup_root / "backup_20260518_120000"
    incomplete = backup_root / "backup_20260518_130000"
    uploads.mkdir(parents=True)
    reports.mkdir()
    backup_uploads = target_backup / "uploads"
    backup_reports = target_backup / "reports"
    backup_uploads.mkdir(parents=True)
    backup_reports.mkdir()
    incomplete.mkdir(parents=True)
    db_path.write_text("current-db", encoding="utf-8")
    (uploads / "current.txt").write_text("current-upload", encoding="utf-8")
    (reports / "current.txt").write_text("current-report", encoding="utf-8")
    (target_backup / "progress_dashboard.db").write_text("backup-db", encoding="utf-8")
    (backup_uploads / "restored.txt").write_text("backup-upload", encoding="utf-8")
    (backup_reports / "restored.txt").write_text("backup-report", encoding="utf-8")
    (target_backup / "backup_info.txt").write_text("info", encoding="utf-8")

    monkeypatch.setattr(maintenance, "_app_root", lambda: app_root)
    monkeypatch.setattr(maintenance, "_safe_app_path", lambda path_value, app_root_arg: str(backup_root) if path_value == "backups" else str(app_root / path_value))
    monkeypatch.setattr(maintenance, "_database_target_path", lambda database_url, app_root_arg: str(db_path))
    monkeypatch.setattr(maintenance, "_restore_target_path", lambda path_value, app_root_arg: str(app_root / path_value))

    with TestClient(app) as client:
        records = client.get("/api/maintenance/backups")
        detail = client.get("/api/maintenance/backups/backup_20260518_120000")
        valid = client.post("/api/maintenance/backups/backup_20260518_120000/validate")
        invalid = client.post("/api/maintenance/backups/backup_20260518_130000/validate")
        missing = client.get("/api/maintenance/backups/not_exists")
        bad_confirm = client.post("/api/maintenance/backups/backup_20260518_120000/restore", json={"confirm_text": "wrong"})
        restore = client.post("/api/maintenance/backups/backup_20260518_120000/restore", json={"confirm_text": "我确认恢复备份"})

    assert records.status_code == 200
    assert detail.status_code == 200
    assert detail.json()["name"] == "backup_20260518_120000"
    assert valid.status_code == 200
    assert valid.json()["validation_status"] == "完整"
    assert invalid.status_code == 200
    assert invalid.json()["validation_status"] == "不完整"
    assert missing.status_code == 404
    assert "未找到指定备份" in missing.json()["detail"]
    assert bad_confirm.status_code == 400
    assert "确认文字不匹配" in bad_confirm.json()["detail"]
    assert restore.status_code == 200
    payload = restore.json()
    assert payload["restored"] is True
    assert payload["restart_required"] is True
    assert payload["pre_restore_backup_name"].endswith("_pre_restore")
    pre_restore_path = Path(payload["pre_restore_backup_path"])
    assert pre_restore_path.exists()
    assert (pre_restore_path / "progress_dashboard.db").read_text(encoding="utf-8") == "current-db"
    assert db_path.read_text(encoding="utf-8") == "backup-db"
    assert (uploads / "restored.txt").exists()
    assert (reports / "restored.txt").exists()

    db = SessionLocal()
    try:
        assert db.query(MaintenanceLog).filter(MaintenanceLog.action == "restore_backup").count() >= 1
    finally:
        db.close()


def test_incomplete_backup_is_rejected_for_restore(tmp_path, monkeypatch) -> None:
    from app.routers import maintenance

    app_root = tmp_path / "app"
    backup_root = app_root / "backups"
    incomplete = backup_root / "backup_incomplete"
    incomplete.mkdir(parents=True)
    monkeypatch.setattr(maintenance, "_app_root", lambda: app_root)
    monkeypatch.setattr(maintenance, "_safe_app_path", lambda path_value, app_root_arg: str(backup_root))

    with TestClient(app) as client:
        response = client.post("/api/maintenance/backups/backup_incomplete/restore", json={"confirm_text": "我确认恢复备份"})

    assert response.status_code == 400
    assert "备份不完整" in response.json()["detail"]







