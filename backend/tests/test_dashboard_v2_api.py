from datetime import date

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.import_batch import ImportBatch
from app.models.progress_item import ProgressItem
from app.models.project import Project
from app.models.rectification_item import RectificationItem


def _seed_dashboard_v2_project() -> tuple[int, int]:
    db = SessionLocal()
    try:
        project = Project(name="T036 Dashboard V2")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="t036.xlsx", sheet_name="机电", status="published", data_date=date(2026, 5, 18))
        db.add(batch)
        db.flush()
        rows = [
            ProgressItem(
                project_id=project.id,
                batch_id=batch.id,
                task_id=1,
                task_name="B2 机电 1层",
                building="B2",
                floor="1层",
                discipline="机电",
                actual_percent=40,
                planned_percent=70,
                progress_deviation=-30,
                planned_start_date=date(2026, 5, 1),
                planned_finish_date=date(2026, 5, 18),
                weight=2,
            ),
            ProgressItem(
                project_id=project.id,
                batch_id=batch.id,
                task_id=2,
                task_name="B2 消防 2层",
                building="B2",
                floor="2层",
                discipline="消防",
                actual_percent=80,
                planned_percent=80,
                progress_deviation=0,
                weight=1,
            ),
            ProgressItem(
                project_id=project.id,
                batch_id=batch.id,
                task_id=3,
                task_name="A1 智能化 1层",
                building="A1",
                floor="1层",
                discipline="智能化",
                actual_percent=90,
                planned_percent=80,
                progress_deviation=10,
                weight=1,
            ),
            ProgressItem(
                project_id=project.id,
                batch_id=batch.id,
                task_id=4,
                task_name="B2 机电 3层",
                building="B2",
                floor="3层",
                discipline="机电",
                actual_percent=0,
                planned_percent=0,
                progress_deviation=None,
                planned_start_date=date(2026, 6, 1),
                planned_finish_date=date(2026, 6, 30),
                schedule_phase="not_started_by_plan",
                status="not_started_by_plan",
                weight=1,
            ),
            ProgressItem(
                project_id=project.id,
                batch_id=batch.id,
                task_id=5,
                task_name="B2 机电 B1层",
                building="B2",
                floor="B1层",
                discipline="机电",
                actual_percent=15,
                planned_percent=18,
                progress_deviation=-3,
                weight=1,
            ),
        ]
        db.add_all(rows)
        db.flush()
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
                task_name="B2 机电 1层",
                delay_level="seriously_delayed",
                status="open",
            )
        )
        db.commit()
        return project.id, batch.id
    finally:
        db.close()


def _seed_project_scope_progress_items() -> tuple[int, str, list[int]]:
    db = SessionLocal()
    try:
        project = Project(name="T047 Project Scope Detail")
        db.add(project)
        db.flush()
        group_id = "group-v47"
        batches: list[ImportBatch] = []
        for sheet_name in ("机电单位", "消防单位", "智能化单位"):
            batch = ImportBatch(
                project_id=project.id,
                file_name="real.xlsx",
                sheet_name=sheet_name,
                import_group_id=group_id,
                status="published",
                data_date=date(2026, 5, 18),
            )
            db.add(batch)
            db.flush()
            batches.append(batch)
        counts = [11, 9, 4]
        task_id = 1
        for batch, count in zip(batches, counts, strict=True):
            for index in range(count):
                item = ProgressItem(
                    project_id=project.id,
                    batch_id=batch.id,
                    task_id=task_id,
                    task_name=f"{batch.sheet_name} B2 2层 {index + 1}",
                    building="B2",
                    floor="2层",
                    discipline=batch.sheet_name.replace("单位", ""),
                    actual_percent=50,
                    planned_percent=60,
                    progress_deviation=-10,
                    weight=1,
                )
                db.add(item)
                db.flush()
                if index == 0:
                    db.add(
                        RectificationItem(
                            project_id=project.id,
                            batch_id=batch.id,
                            progress_item_id=item.id,
                            source_type="progress_item",
                            source_id=item.id,
                            discipline=item.discipline,
                            building=item.building,
                            floor=item.floor,
                            task_name=item.task_name,
                            delay_level="delayed",
                            status="open",
                        )
                    )
                task_id += 1
        db.commit()
        return project.id, group_id, [batch.id for batch in batches]
    finally:
        db.close()


def test_dashboard_v2_overview_returns_project_summary() -> None:
    project_id, batch_id = _seed_dashboard_v2_project()
    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/dashboard-v2", params={"batch_id": batch_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"]["view_mode"] == "overview"
    assert payload["overview"]["item_count"] == 5
    assert payload["discipline_cards"]
    assert payload["building_cards"]
    assert payload["floor_heatmap"]
    assert payload["building_elevation"]


def test_dashboard_v2_discipline_returns_discipline_cards() -> None:
    project_id, batch_id = _seed_dashboard_v2_project()
    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/dashboard-v2", params={"view_mode": "discipline", "batch_id": batch_id})

    assert response.status_code == 200
    cards = response.json()["discipline_cards"]
    assert {row["name"] for row in cards} == {"机电", "消防", "智能化"}


def test_dashboard_v2_building_returns_building_cards() -> None:
    project_id, batch_id = _seed_dashboard_v2_project()
    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/dashboard-v2", params={"view_mode": "building", "batch_id": batch_id})

    assert response.status_code == 200
    cards = response.json()["building_cards"]
    assert {row["name"] for row in cards} == {"A1", "B2"}


def test_dashboard_v2_building_filter_keeps_overview_and_graph_consistent() -> None:
    project_id, batch_id = _seed_dashboard_v2_project()
    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/dashboard-v2", params={"batch_id": batch_id, "building": "B2"})

    payload = response.json()
    assert response.status_code == 200
    assert payload["overview"]["item_count"] == 4
    assert sum(row["task_count"] for row in payload["building_cards"]) == payload["overview"]["item_count"]
    assert {row["building"] for row in payload["floor_heatmap"]} == {"B2"}
    assert {row["building"] for row in payload["building_elevation"]} == {"B2"}


def test_dashboard_v2_discipline_filter_keeps_overview_and_graph_consistent() -> None:
    project_id, batch_id = _seed_dashboard_v2_project()
    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/dashboard-v2", params={"batch_id": batch_id, "discipline": "机电"})

    payload = response.json()
    assert response.status_code == 200
    assert payload["overview"]["item_count"] == 3
    assert sum(row["task_count"] for row in payload["discipline_cards"]) == payload["overview"]["item_count"]
    assert {row["discipline"] for row in payload["discipline_cards"]} == {"机电"}
    assert payload["building_elevation"][0]["floors"]


def test_dashboard_v2_weight_normalized_statistics_are_correct() -> None:
    project_id, batch_id = _seed_dashboard_v2_project()
    with TestClient(app) as client:
        response = client.get(
            f"/api/projects/{project_id}/dashboard-v2",
            params={"batch_id": batch_id, "calculation_method": "weighted_percent"},
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["overview"]["actual_percent"] == 44.1667
    assert payload["overview"]["planned_percent"] == 63
    assert payload["calculation_context"]["weight_total"] == 6
    assert payload["calculation_context"]["participating_task_count"] == 5


def test_dashboard_v2_empty_project_returns_empty_arrays_without_500() -> None:
    with TestClient(app) as client:
        project_id = client.post("/api/projects", json={"name": "empty dashboard v2"}).json()["id"]
        response = client.get(f"/api/projects/{project_id}/dashboard-v2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["overview"] is None
    assert payload["discipline_cards"] == []
    assert payload["building_cards"] == []
    assert payload["floor_heatmap"] == []
    assert payload["building_elevation"] == []
    assert payload["delayed_items"] == []
    assert payload["scope"]["message"]


def test_dashboard_v2_response_includes_adaptation_diagnostics() -> None:
    project_id, batch_id = _seed_dashboard_v2_project()
    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/dashboard-v2", params={"batch_id": batch_id})

    payload = response.json()
    assert response.status_code == 200
    assert payload["calculation_diagnostics"]["recommended_calculation_method"] == "weighted_percent"
    assert payload["dashboard_capabilities"]["building_view"]["available"] is True
    assert payload["dashboard_capabilities"]["floor_heatmap"]["available"] is True


def test_dashboard_v2_project_scope_diagnostics_use_aggregated_items() -> None:
    project_id, group_id, _ = _seed_project_scope_progress_items()
    with TestClient(app) as client:
        response = client.get(
            f"/api/projects/{project_id}/dashboard-v2",
            params={"import_group_id": group_id},
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["overview"]["batch_id"] is None
    assert payload["floor_heatmap"]
    assert payload["calculation_context"]["calculation_method"] == "weighted_percent"
    assert payload["calculation_diagnostics"]["recommended_calculation_method"] == "weighted_percent"
    assert payload["calculation_diagnostics"]["recommended_calculation_method_name"] == "权重统计"
    assert payload["calculation_diagnostics"]["recommended_reason"] == "检测到 Excel 中存在权重字段"
    methods = payload["calculation_diagnostics"]["available_calculation_methods"]
    weighted = next(method for method in methods if method["code"] == "weighted_percent")
    task_average = next(method for method in methods if method["code"] == "task_average")
    assert weighted["available"] is True
    assert weighted["recommended"] is True
    assert task_average["recommended"] is False
    assert payload["dashboard_capabilities"]["discipline_view"]["available"] is True
    assert payload["dashboard_capabilities"]["building_view"]["available"] is True
    assert payload["dashboard_capabilities"]["floor_heatmap"]["available"] is True
    assert payload["dashboard_capabilities"]["percent_average"]["available"] is True


def test_dashboard_v2_building_elevation_status_and_floor_sorting() -> None:
    project_id, batch_id = _seed_dashboard_v2_project()
    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/dashboard-v2", params={"view_mode": "building", "batch_id": batch_id, "building": "B2"})

    payload = response.json()
    assert response.status_code == 200
    b2 = payload["building_elevation"][0]
    assert b2["building"] == "B2"
    floors = b2["floors"]
    assert [row["floor"] for row in floors] == ["3层", "2层", "1层", "B1层"]
    by_floor = {row["floor"]: row for row in floors}
    assert by_floor["1层"]["status"] == "seriously_delayed"
    assert by_floor["1层"]["status_label"] == "严重滞后"
    assert by_floor["1层"]["serious_delayed_count"] == 1
    assert by_floor["3层"]["status"] == "not_started_by_plan"
    assert by_floor["3层"]["status_label"] == "未到计划开始"
    assert by_floor["3层"]["not_started_count"] == 1
    assert by_floor["2层"]["status"] == "normal"


def test_dashboard_v2_floor_status_uses_aggregate_deviation_not_single_task_worst_case() -> None:
    db = SessionLocal()
    try:
        project = Project(name="T050 heatmap status consistency")
        db.add(project)
        db.flush()
        batch = ImportBatch(
            project_id=project.id,
            file_name="t050.xlsx",
            sheet_name="机电",
            status="published",
            data_date=date(2026, 5, 18),
        )
        db.add(batch)
        db.flush()
        db.add_all(
            [
                ProgressItem(
                    project_id=project.id,
                    batch_id=batch.id,
                    task_id=1001,
                    task_name="B2 2层 严重滞后项",
                    building="B2",
                    floor="2层",
                    discipline="机电",
                    actual_percent=40,
                    planned_percent=70,
                    progress_deviation=-30,
                    planned_start_date=date(2026, 5, 1),
                    planned_finish_date=date(2026, 5, 18),
                ),
                ProgressItem(
                    project_id=project.id,
                    batch_id=batch.id,
                    task_id=1002,
                    task_name="B2 2层 超前项",
                    building="B2",
                    floor="2层",
                    discipline="消防",
                    actual_percent=100,
                    planned_percent=50,
                    progress_deviation=50,
                ),
            ]
        )
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/dashboard-v2", params={"view_mode": "building", "batch_id": batch_id})

    payload = response.json()
    assert response.status_code == 200
    heatmap_cell = next(row for row in payload["floor_heatmap"] if row["building"] == "B2" and row["floor"] == "2层")
    elevation_floor = next(row for row in payload["building_elevation"][0]["floors"] if row["floor"] == "2层")
    assert heatmap_cell["progress_deviation"] == -5
    assert heatmap_cell["status"] == elevation_floor["status"] == "normal"
    assert heatmap_cell["status_label"] == elevation_floor["status_label"] == "正常"
    assert heatmap_cell["serious_delayed_count"] == elevation_floor["serious_delayed_count"] == 1


def test_progress_items_project_scope_import_group_returns_all_batches() -> None:
    project_id, group_id, batch_ids = _seed_project_scope_progress_items()
    with TestClient(app) as client:
        response = client.get(
            f"/api/projects/{project_id}/progress-items",
            params={"scope": "project", "import_group_id": group_id, "building": "B2", "floor": "2层", "page_size": 100},
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["total"] == 24
    assert payload["scope_info"]["scope"] == "project"
    assert payload["scope_info"]["included_batch_ids"] == batch_ids
    assert payload["scope_info"]["included_sheets"] == ["机电单位", "消防单位", "智能化单位"]


def test_progress_items_project_scope_data_date_and_batch_ids() -> None:
    project_id, _, batch_ids = _seed_project_scope_progress_items()
    with TestClient(app) as client:
        by_date = client.get(
            f"/api/projects/{project_id}/progress-items",
            params={"scope": "project", "data_date": "2026-05-18", "building": "B2", "floor": "2层", "page_size": 100},
        )
        by_ids = client.get(
            f"/api/projects/{project_id}/progress-items",
            params={"scope": "project", "batch_ids": f"{batch_ids[0]},{batch_ids[2]}", "building": "B2", "floor": "2层", "page_size": 100},
        )

    assert by_date.status_code == 200
    assert by_date.json()["total"] == 24
    assert by_ids.status_code == 200
    assert by_ids.json()["total"] == 15


def test_progress_items_project_scope_batch_ids_take_precedence_over_data_date_and_items_alias() -> None:
    project_id, _, batch_ids = _seed_project_scope_progress_items()
    with TestClient(app) as client:
        response = client.get(
            f"/api/projects/{project_id}/items",
            params={
                "scope": "project",
                "data_date": "2026-05-18",
                "batch_ids": f"{batch_ids[2]}",
                "building": "B2",
                "floor": "2层",
                "page_size": 100,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 4
    assert payload["scope_info"]["included_batch_ids"] == [batch_ids[2]]


def test_rectifications_project_scope_and_summary_use_multiple_batches() -> None:
    project_id, group_id, batch_ids = _seed_project_scope_progress_items()
    with TestClient(app) as client:
        list_response = client.get(
            f"/api/projects/{project_id}/rectifications",
            params={"scope": "project", "import_group_id": group_id, "building": "B2", "floor": "2层", "page_size": 100},
        )
        summary_response = client.get(
            f"/api/projects/{project_id}/rectifications/summary",
            params={"scope": "project", "batch_ids": ",".join(str(row) for row in batch_ids)},
        )

    assert list_response.status_code == 200
    assert list_response.json()["total"] == 3
    assert summary_response.status_code == 200
    assert summary_response.json()["total"] == 3


def test_dashboard_export_project_scope_uses_filtered_multi_batch_range() -> None:
    project_id, group_id, batch_ids = _seed_project_scope_progress_items()
    with TestClient(app) as client:
        response = client.get(
            f"/api/projects/{project_id}/reports/dashboard-export",
            params={"scope": "project", "import_group_id": group_id, "building": "B2", "floor": "2层"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def test_progress_items_single_batch_and_latest_defaults_still_work() -> None:
    project_id, _, batch_ids = _seed_project_scope_progress_items()
    with TestClient(app) as client:
        single = client.get(
            f"/api/projects/{project_id}/progress-items",
            params={"batch_id": batch_ids[2], "building": "B2", "floor": "2层", "page_size": 100},
        )
        latest_default = client.get(
            f"/api/projects/{project_id}/progress-items",
            params={"building": "B2", "floor": "2层", "page_size": 100},
        )

    assert single.status_code == 200
    assert single.json()["total"] == 4
    assert single.json()["scope_info"]["scope"] == "batch"
    assert latest_default.status_code == 200
    assert latest_default.json()["total"] == 4
    assert latest_default.json()["scope_info"]["message"] == "当前显示最新单批次明细。"
