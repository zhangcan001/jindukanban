from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.import_batch import ImportBatch
from app.models.progress_item import ProgressItem
from app.models.project import Project
from app.models.rectification_item import RectificationItem
from app.models.warning_record import WarningRecord


def _seed_unified_project() -> tuple[int, int]:
    db = SessionLocal()
    try:
        project = Project(name="T035 统一看板")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="t035.xlsx", sheet_name="机电", status="published", data_date=date(2026, 5, 18), data_quality_score=88)
        db.add(batch)
        db.flush()
        rows = [
            ProgressItem(
                project_id=project.id,
                batch_id=batch.id,
                task_id=101,
                construction_unit="甲安装",
                task_name="B2 机电 1F",
                building="B2",
                floor="1层",
                discipline="机电",
                system_name="强电",
                actual_percent=40,
                planned_percent=70,
                progress_deviation=-30,
                status="seriously_delayed",
                planned_start_date=date(2026, 5, 1),
                planned_finish_date=date(2026, 5, 18),
                weight=0.4,
            ),
            ProgressItem(
                project_id=project.id,
                batch_id=batch.id,
                task_id=102,
                construction_unit="甲安装",
                task_name="B2 消防 2F",
                building="B2",
                floor="2层",
                discipline="消防",
                system_name="喷淋",
                actual_percent=80,
                planned_percent=80,
                progress_deviation=0,
                status="normal",
                weight=0.3,
            ),
            ProgressItem(
                project_id=project.id,
                batch_id=batch.id,
                task_id=103,
                construction_unit="乙智能化",
                task_name="A1 智能化 1F",
                building="A1",
                floor="1层",
                discipline="智能化",
                system_name="弱电",
                actual_percent=90,
                planned_percent=80,
                progress_deviation=10,
                status="ahead",
                weight=0.3,
            ),
        ]
        db.add_all(rows)
        db.flush()
        db.add(WarningRecord(project_id=project.id, batch_id=batch.id, task_id=101, level="critical", title="严重滞后", message="B2 机电滞后"))
        db.add(
            RectificationItem(
                project_id=project.id,
                batch_id=batch.id,
                progress_item_id=rows[0].id,
                source_type="progress_item",
                source_id=rows[0].id,
                discipline="机电",
                building="B2",
                floor="1层",
                system_name="强电",
                task_name="B2 机电 1F",
                delay_level="seriously_delayed",
                status="open",
            )
        )
        db.commit()
        return project.id, batch.id
    finally:
        db.close()


def test_dashboard_unified_unfiltered_returns_full_scope() -> None:
    project_id, batch_id = _seed_unified_project()
    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/analytics/dashboard-unified", params={"batch_id": batch_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["overview"]["item_count"] == 3
    assert {row["name"] for row in payload["by_construction_unit"]} == {"甲安装", "乙智能化"}
    assert {row["name"] for row in payload["by_building"]} == {"A1", "B2"}
    assert payload["warning_summary"]["total"] == 1
    assert payload["rectification_summary"]["total"] == 1


def test_dashboard_unified_construction_unit_filter_keeps_modules_consistent() -> None:
    project_id, batch_id = _seed_unified_project()
    with TestClient(app) as client:
        response = client.get(
            f"/api/projects/{project_id}/analytics/dashboard-unified",
            params={"batch_id": batch_id, "construction_unit": "甲安装"},
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["overview"]["item_count"] == 2
    assert {row["name"] for row in payload["by_construction_unit"]} == {"甲安装"}
    assert {row["name"] for row in payload["by_building"]} == {"B2"}
    assert all(item["construction_unit"] == "甲安装" for item in payload["delayed_items"])


def test_dashboard_unified_dimension_and_combination_filters_are_consistent() -> None:
    project_id, batch_id = _seed_unified_project()
    with TestClient(app) as client:
        by_building = client.get(f"/api/projects/{project_id}/analytics/dashboard-unified", params={"batch_id": batch_id, "building": "B2"}).json()
        by_floor = client.get(f"/api/projects/{project_id}/analytics/dashboard-unified", params={"batch_id": batch_id, "floor": "1层"}).json()
        by_discipline = client.get(f"/api/projects/{project_id}/analytics/dashboard-unified", params={"batch_id": batch_id, "discipline": "机电"}).json()
        combined = client.get(
            f"/api/projects/{project_id}/analytics/dashboard-unified",
            params={"batch_id": batch_id, "construction_unit": "甲安装", "building": "B2", "floor": "1层", "discipline": "机电"},
        ).json()

    assert by_building["overview"]["item_count"] == sum(row["task_count"] for row in by_building["by_building"])
    assert by_floor["overview"]["item_count"] == sum(row["task_count"] for row in by_floor["by_floor"])
    assert by_discipline["overview"]["item_count"] == sum(row["task_count"] for row in by_discipline["by_discipline"])
    assert combined["overview"]["item_count"] == 1
    assert combined["warning_summary"]["total"] == 1
    assert combined["rectification_summary"]["total"] == 1
    assert len(combined["delayed_items"]) == 1
