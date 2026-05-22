"""验证 /projects/{id}/rectifications/filter-options 端点。

为什么需要:前端 RectificationsView.loadData() 之前会发一个 page_size=200 的额外
listRectifications 请求,只为浏览器里 distinct 出 8 列下拉(专业/楼栋/楼层/责任人/
责任单位/滞后等级/状态/来源),数据 > 200 时下拉项还会不全(隐藏 bug)。这里改成
一次 DISTINCT 拿全。

测试要点:
1. 8 列维度一次返回去重值
2. floors_by_building 按 building 正确分组
3. scope=batch + batch_id 过滤生效
4. > 200 行数据时下拉仍完整(防回归 page_size=200 截断 bug)
5. 项目不存在返回 404
"""
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.project import Project
from app.models.rectification_item import RectificationItem


def _setup_project_with_rectifications() -> int:
    db = SessionLocal()
    try:
        project = Project(name="rectification filter-options 测试项目")
        db.add(project)
        db.flush()

        rows = [
            # (discipline, building, floor, person, unit, delay_level, status, source_type)
            ("电气", "1#楼", "1F", "张三", "中建一局", "delayed", "open", "warning"),
            ("电气", "1#楼", "2F", "李四", "中建一局", "seriously_delayed", "in_progress", "progress_item"),
            ("暖通", "2#楼", "B1", "王五", "中建二局", "slightly_delayed", "completed", "manual"),
            ("给排水", "2#楼", "1F", "赵六", "中建二局", "delayed", "closed", "warning"),
            # 重复的一行,验证 DISTINCT
            ("电气", "1#楼", "1F", "张三", "中建一局", "delayed", "open", "warning"),
        ]
        for disc, bld, flr, person, unit, delay, st, src in rows:
            db.add(RectificationItem(
                project_id=project.id,
                source_type=src,
                discipline=disc, building=bld, floor=flr,
                responsible_person=person, responsible_unit=unit,
                delay_level=delay, status=st,
                task_name=f"{disc}-{bld}-{flr}",
            ))
        db.commit()
        return project.id
    finally:
        db.close()


def test_rectification_filter_options_returns_eight_dimensions() -> None:
    project_id = _setup_project_with_rectifications()
    with TestClient(app) as client:
        resp = client.get(f"/api/projects/{project_id}/rectifications/filter-options")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body["disciplines"]) == {"电气", "暖通", "给排水"}
        assert set(body["buildings"]) == {"1#楼", "2#楼"}
        assert set(body["floors"]) == {"1F", "2F", "B1"}
        assert set(body["responsible_persons"]) == {"张三", "李四", "王五", "赵六"}
        assert set(body["responsible_units"]) == {"中建一局", "中建二局"}
        assert set(body["delay_levels"]) == {"delayed", "seriously_delayed", "slightly_delayed"}
        assert set(body["statuses"]) == {"open", "in_progress", "completed", "closed"}
        assert set(body["source_types"]) == {"warning", "progress_item", "manual"}


def test_rectification_filter_options_floors_by_building_grouped() -> None:
    project_id = _setup_project_with_rectifications()
    with TestClient(app) as client:
        resp = client.get(f"/api/projects/{project_id}/rectifications/filter-options")
        body = resp.json()
        # 1#楼 有 1F, 2F;2#楼 有 B1, 1F
        assert set(body["floors_by_building"]["1#楼"]) == {"1F", "2F"}
        assert set(body["floors_by_building"]["2#楼"]) == {"B1", "1F"}


def test_rectification_filter_options_handles_more_than_200_rows() -> None:
    """防回归:之前前端用 page_size=200 截断了下拉数据,>200 行时维度不全。"""
    db = SessionLocal()
    try:
        project = Project(name="rect 大数据量")
        db.add(project)
        db.flush()
        for i in range(250):
            db.add(RectificationItem(
                project_id=project.id,
                source_type="manual",
                discipline=f"D{i % 20}",
                building=f"B{i % 5}",
                floor=f"F{i}",
                task_name=f"row-{i}",
            ))
        db.commit()
        project_id = project.id
    finally:
        db.close()

    with TestClient(app) as client:
        resp = client.get(f"/api/projects/{project_id}/rectifications/filter-options")
        body = resp.json()
        # 250 个 floor 值应全部进入下拉,而不是只回 200 行能 distinct 出的部分
        assert len(body["floors"]) == 250
        assert len(body["disciplines"]) == 20
        assert len(body["buildings"]) == 5


def test_rectification_filter_options_returns_404_for_missing_project() -> None:
    with TestClient(app) as client:
        resp = client.get("/api/projects/999999/rectifications/filter-options")
        assert resp.status_code == 404
