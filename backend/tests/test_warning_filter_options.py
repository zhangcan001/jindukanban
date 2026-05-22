"""验证 /projects/{id}/warnings/filter-options 端点。

为什么需要:前端 WarningsView 在 loadOptionRecords 里把当前批次的全部预警拉回来
浏览器里 distinct,每次切批次都要重复一次,而且预警维度本来就来自 ProgressItem
(预警表自己不存 discipline/building/floor)。这里一条 JOIN+DISTINCT 拿完。

测试要点:
1. 一次拿到 discipline/building/floor 去重值
2. floors_by_building 按 building 正确分组
3. batch_id 过滤生效
4. 没有关联 ProgressItem 的预警(task_id=NULL,如数据质量类)不污染下拉
5. 项目不存在返回 404
"""
from datetime import date

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.import_batch import ImportBatch
from app.models.progress_item import ProgressItem
from app.models.progress_task import ProgressTask
from app.models.project import Project
from app.models.warning_record import WarningRecord


def _setup_project_with_warnings() -> tuple[int, int, int]:
    """造两个 batch、若干 ProgressItem + WarningRecord(含 task_id=NULL 的数据质量预警)。"""
    db = SessionLocal()
    try:
        project = Project(name="warning filter-options 测试项目")
        db.add(project)
        db.flush()

        batch_a = ImportBatch(
            project_id=project.id,
            file_name="a.xlsx",
            status="published",
            is_active=True,
            data_date=date(2026, 5, 20),
        )
        batch_b = ImportBatch(
            project_id=project.id,
            file_name="b.xlsx",
            status="published",
            is_active=True,
            data_date=date(2026, 5, 22),
        )
        db.add_all([batch_a, batch_b])
        db.flush()

        # 4 个 task,用来给 ProgressItem 关联 task_id
        tasks = [ProgressTask(project_id=project.id, task_name=f"t{i}", discipline="-") for i in range(4)]
        db.add_all(tasks)
        db.flush()

        # batch_a: 2 行(电气/1#楼/1F, 暖通/1#楼/2F)
        # batch_b: 2 行(给排水/2#楼/B1, 电气/1#楼/3F)
        rows_a = [
            (tasks[0].id, "电气", "1#楼", "1F"),
            (tasks[1].id, "暖通", "1#楼", "2F"),
        ]
        rows_b = [
            (tasks[2].id, "给排水", "2#楼", "B1"),
            (tasks[3].id, "电气", "1#楼", "3F"),
        ]
        for tid, disc, bld, flr in rows_a:
            db.add(ProgressItem(
                project_id=project.id, batch_id=batch_a.id, task_id=tid,
                discipline=disc, building=bld, floor=flr,
                task_name=f"{disc}-{bld}-{flr}",
            ))
        for tid, disc, bld, flr in rows_b:
            db.add(ProgressItem(
                project_id=project.id, batch_id=batch_b.id, task_id=tid,
                discipline=disc, building=bld, floor=flr,
                task_name=f"{disc}-{bld}-{flr}",
            ))

        # 每行至少一条 warning,batch_a 还塞一条 task_id=NULL 的数据质量预警(不应出现在下拉里)
        warnings = []
        for tid, *_ in rows_a:
            warnings.append(WarningRecord(
                project_id=project.id, batch_id=batch_a.id, task_id=tid,
                level="warning", message="进度滞后",
            ))
        for tid, *_ in rows_b:
            warnings.append(WarningRecord(
                project_id=project.id, batch_id=batch_b.id, task_id=tid,
                level="warning", message="进度滞后",
            ))
        warnings.append(WarningRecord(
            project_id=project.id, batch_id=batch_a.id, task_id=None,
            level="info", message="数据质量异常",
        ))
        db.add_all(warnings)
        db.commit()
        return project.id, batch_a.id, batch_b.id
    finally:
        db.close()


def test_warning_filter_options_returns_distinct_dimensions() -> None:
    project_id, _, _ = _setup_project_with_warnings()
    with TestClient(app) as client:
        resp = client.get(f"/api/projects/{project_id}/warnings/filter-options")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body["disciplines"]) == {"电气", "暖通", "给排水"}
        assert set(body["buildings"]) == {"1#楼", "2#楼"}
        assert set(body["floors"]) == {"1F", "2F", "3F", "B1"}


def test_warning_filter_options_floors_by_building_grouped() -> None:
    project_id, _, _ = _setup_project_with_warnings()
    with TestClient(app) as client:
        resp = client.get(f"/api/projects/{project_id}/warnings/filter-options")
        body = resp.json()
        assert set(body["floors_by_building"]["1#楼"]) == {"1F", "2F", "3F"}
        assert set(body["floors_by_building"]["2#楼"]) == {"B1"}


def test_warning_filter_options_filtered_by_batch_id() -> None:
    """指定 batch_id 后,只返回该批次相关预警的下拉。"""
    project_id, batch_a_id, _ = _setup_project_with_warnings()
    with TestClient(app) as client:
        resp = client.get(f"/api/projects/{project_id}/warnings/filter-options", params={"batch_id": batch_a_id})
        body = resp.json()
        # batch_a 只有 电气/1F + 暖通/2F,都在 1#楼
        assert set(body["disciplines"]) == {"电气", "暖通"}
        assert set(body["buildings"]) == {"1#楼"}
        assert set(body["floors"]) == {"1F", "2F"}


def test_warning_filter_options_excludes_data_quality_warnings() -> None:
    """task_id=NULL 的数据质量预警没有 ProgressItem 维度,INNER JOIN 自然排除——
    下拉里绝不应该出现这类预警贡献的脏数据(因为它就没有这些字段)。
    这个测试用的是它"不会让下拉变更大"——即结果与不存在该预警时一致。"""
    project_id, _, _ = _setup_project_with_warnings()
    with TestClient(app) as client:
        resp = client.get(f"/api/projects/{project_id}/warnings/filter-options")
        body = resp.json()
        # disciplines 内不应该出现 None / 空串
        assert all(v for v in body["disciplines"])
        assert all(v for v in body["buildings"])
        assert all(v for v in body["floors"])


def test_warning_filter_options_returns_404_for_missing_project() -> None:
    with TestClient(app) as client:
        resp = client.get("/api/projects/999999/warnings/filter-options")
        assert resp.status_code == 404
