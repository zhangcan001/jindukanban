"""验证 /projects/{id}/progress-items/filter-options 端点。

为什么需要:前端原来要 while True 翻光所有 ProgressItem(200 条/页)只为去重出
施工单位/楼栋/楼层/专业/系统/状态六列文本。批次稍大切换就要好几个串行 HTTP,
切批次卡顿是一线工程师反复抱怨的。这里加单测覆盖三个关键点:
1. 一次请求拿到所有维度的去重选项
2. floors_by_building 按 building 联动正确
3. 项目不存在 / 无可见批次 返回合理结果
"""
from datetime import date

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.import_batch import ImportBatch
from app.models.progress_item import ProgressItem
from app.models.project import Project


def _setup_project_with_items() -> int:
    """建一个 project + published batch + 5 行 ProgressItem,覆盖多种维度组合。"""
    db = SessionLocal()
    try:
        project = Project(name="filter-options 测试项目")
        db.add(project)
        db.flush()
        batch = ImportBatch(
            project_id=project.id,
            file_name="t.xlsx",
            status="published",
            is_active=True,
            data_date=date(2026, 5, 22),
        )
        db.add(batch)
        db.flush()

        rows = [
            # (construction_unit, building, floor, discipline, system_name, status)
            ("中建一局", "1#楼", "1F", "电气", "强电", "normal"),
            ("中建一局", "1#楼", "2F", "电气", "强电", "delayed"),
            ("中建一局", "1#楼", "2F", "暖通", "送排风", "normal"),
            ("中建二局", "2#楼", "B1", "给排水", "消防水", "ahead"),
            ("中建二局", "2#楼", "1F", "给排水", "消防水", "normal"),
        ]
        for cu, bld, flr, disc, sysn, st in rows:
            db.add(
                ProgressItem(
                    project_id=project.id,
                    batch_id=batch.id,
                    construction_unit=cu,
                    building=bld,
                    floor=flr,
                    discipline=disc,
                    system_name=sysn,
                    status=st,
                    task_name=f"{sysn}-{bld}-{flr}",
                )
            )
        db.commit()
        return project.id
    finally:
        db.close()


def test_filter_options_returns_distinct_values_per_dimension() -> None:
    project_id = _setup_project_with_items()
    with TestClient(app) as client:
        resp = client.get(f"/api/projects/{project_id}/progress-items/filter-options")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body["construction_units"]) == {"中建一局", "中建二局"}
        assert set(body["buildings"]) == {"1#楼", "2#楼"}
        assert set(body["floors"]) == {"1F", "2F", "B1"}
        assert set(body["disciplines"]) == {"电气", "暖通", "给排水"}
        assert set(body["system_names"]) == {"强电", "送排风", "消防水"}
        assert set(body["statuses"]) == {"normal", "delayed", "ahead"}


def test_filter_options_floors_by_building_is_correctly_grouped() -> None:
    """1#楼 不应该出现 B1(那是 2#楼的);2#楼 不应该出现 2F。"""
    project_id = _setup_project_with_items()
    with TestClient(app) as client:
        resp = client.get(f"/api/projects/{project_id}/progress-items/filter-options")
        assert resp.status_code == 200, resp.text
        floors_by_building = resp.json()["floors_by_building"]
        assert set(floors_by_building["1#楼"]) == {"1F", "2F"}
        assert set(floors_by_building["2#楼"]) == {"B1", "1F"}


def test_filter_options_returns_empty_when_no_published_batch() -> None:
    """新建项目还没发布过任何批次时应该返回全空数组,而不是 500。"""
    db = SessionLocal()
    try:
        project = Project(name="无批次项目")
        db.add(project)
        db.commit()
        project_id = project.id
    finally:
        db.close()

    with TestClient(app) as client:
        resp = client.get(f"/api/projects/{project_id}/progress-items/filter-options")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["buildings"] == []
        assert body["floors_by_building"] == {}


def test_filter_options_returns_404_when_project_missing() -> None:
    with TestClient(app) as client:
        resp = client.get("/api/projects/999999/progress-items/filter-options")
        assert resp.status_code == 404
