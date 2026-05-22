from datetime import date

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.import_batch import ImportBatch
from app.models.progress_item import ProgressItem
from app.models.project import Project
from app.services.analytics_service import group_items_multi


def _seed_attribution_dataset() -> int:
    """造一份多专业 × 多施工单位 × 多楼层的小数据集。"""
    db = SessionLocal()
    try:
        project = Project(name="偏差归因测试")
        db.add(project)
        db.flush()
        batch = ImportBatch(
            project_id=project.id,
            file_name="attribution.xlsx",
            status="published",
            data_date=date(2026, 5, 20),
        )
        db.add(batch)
        db.flush()
        db.add_all(
            [
                # 中建八局-电气-1F:严重滞后 (deviation = -30)
                ProgressItem(
                    project_id=project.id, batch_id=batch.id, task_name="桥架-A",
                    construction_unit="中建八局", discipline="电气", floor="1F",
                    actual_percent=20.0, planned_percent=50.0,
                ),
                ProgressItem(
                    project_id=project.id, batch_id=batch.id, task_name="桥架-B",
                    construction_unit="中建八局", discipline="电气", floor="1F",
                    actual_percent=20.0, planned_percent=50.0,
                ),
                # 中建八局-给排水-2F:轻微超前 (deviation = +5)
                ProgressItem(
                    project_id=project.id, batch_id=batch.id, task_name="给水管-A",
                    construction_unit="中建八局", discipline="给排水", floor="2F",
                    actual_percent=55.0, planned_percent=50.0,
                ),
                # 中建一局-暖通-1F:正常 (deviation = 0)
                ProgressItem(
                    project_id=project.id, batch_id=batch.id, task_name="风管-A",
                    construction_unit="中建一局", discipline="暖通", floor="1F",
                    actual_percent=60.0, planned_percent=60.0,
                ),
            ]
        )
        db.commit()
        return project.id
    finally:
        db.close()


def test_group_items_multi_keys_combine_dimensions() -> None:
    db = SessionLocal()
    try:
        project = Project(name="多维分组单元测试")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="x.xlsx", status="published")
        db.add(batch)
        db.flush()
        items = [
            ProgressItem(project_id=project.id, batch_id=batch.id, task_name="t1",
                         construction_unit="A", discipline="电气", floor="1F"),
            ProgressItem(project_id=project.id, batch_id=batch.id, task_name="t2",
                         construction_unit="A", discipline="电气", floor="1F"),
            ProgressItem(project_id=project.id, batch_id=batch.id, task_name="t3",
                         construction_unit="A", discipline="给排水", floor="1F"),
            ProgressItem(project_id=project.id, batch_id=batch.id, task_name="t4",
                         construction_unit=None, discipline=None, floor=None),
        ]
        db.add_all(items)
        db.commit()
        groups = group_items_multi(items, ["construction_unit", "discipline", "floor"])
        assert ("A", "电气", "1F") in groups
        assert len(groups[("A", "电气", "1F")]) == 2
        assert ("A", "给排水", "1F") in groups
        # 空值用 fallback 占位
        empty_key = ("未填写", "未填写", "未填写楼层")
        assert empty_key in groups
    finally:
        db.close()


def test_deviation_attribution_endpoint_returns_rows_sorted_by_abs_deviation() -> None:
    project_id = _seed_attribution_dataset()
    with TestClient(app) as client:
        response = client.get(
            f"/api/projects/{project_id}/analytics/deviation-attribution",
            params={"dimensions": "construction_unit,discipline,floor"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["dimensions"] == ["construction_unit", "discipline", "floor"]
    assert payload["total_count"] == 4
    rows = payload["rows"]
    assert len(rows) == 3  # 3 个 (unit, discipline, floor) 组合
    # 最严重的偏差应当排第一:中建八局-电气-1F, deviation = -30
    first = rows[0]
    assert first["dimension_values"] == {
        "construction_unit": "中建八局",
        "discipline": "电气",
        "floor": "1F",
    }
    assert first["progress_deviation"] == -30.0
    assert first["abs_deviation"] == 30.0
    assert first["count"] == 2
    # contribution = deviation * (group_count / total_count) = -30 * 0.5 = -15
    assert first["contribution"] == -15.0
    # 中建一局-暖通-1F deviation=0 排末位
    last = rows[-1]
    assert last["dimension_values"]["construction_unit"] == "中建一局"
    assert last["progress_deviation"] == 0.0


def test_deviation_attribution_endpoint_respects_top_n() -> None:
    project_id = _seed_attribution_dataset()
    with TestClient(app) as client:
        response = client.get(
            f"/api/projects/{project_id}/analytics/deviation-attribution",
            params={"dimensions": "construction_unit,discipline,floor", "top_n": 1},
        )
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["progress_deviation"] == -30.0


def test_deviation_attribution_endpoint_validates_dimension_count_and_names() -> None:
    project_id = _seed_attribution_dataset()
    with TestClient(app) as client:
        bad_dim = client.get(
            f"/api/projects/{project_id}/analytics/deviation-attribution",
            params={"dimensions": "not_a_real_dimension"},
        )
        too_many = client.get(
            f"/api/projects/{project_id}/analytics/deviation-attribution",
            params={"dimensions": "construction_unit,discipline,floor,building"},
        )
        empty = client.get(
            f"/api/projects/{project_id}/analytics/deviation-attribution",
            params={"dimensions": ""},
        )
    assert bad_dim.status_code == 400
    assert too_many.status_code == 400
    assert empty.status_code == 400


def test_deviation_attribution_endpoint_supports_single_dimension() -> None:
    project_id = _seed_attribution_dataset()
    with TestClient(app) as client:
        response = client.get(
            f"/api/projects/{project_id}/analytics/deviation-attribution",
            params={"dimensions": "discipline"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["dimensions"] == ["discipline"]
    rows = payload["rows"]
    # 3 个专业 (电气、给排水、暖通) → 3 行
    assert len(rows) == 3
    assert {row["dimension_values"]["discipline"] for row in rows} == {"电气", "给排水", "暖通"}
