"""U-P1c: 验证 /progress-items/{id}/undo-last-edit 的"撤销最近一次修改"语义。

场景：一线值班工程师在看板上手改了某个明细行的实际完成率,刚保存就发现填错了。
之前要么得拼命回忆原值再 PUT 一次,要么去翻 edit_history 手动改数据库。本测试覆盖
单次撤销、连续两次撤销、冻结批次拒绝撤销、空历史拒绝撤销、撤销最后一条历史时
is_manually_edited 应被自动清掉等关键路径。
"""
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models.import_batch import ImportBatch
from app.models.progress_item import ProgressItem
from app.models.progress_item_edit_history import ProgressItemEditHistory
from app.models.project import Project


def _setup_progress_item(*, frozen: bool = False) -> tuple[int, int, int]:
    """建一个 project → batch(imported) → progress_item,返回三者 id。"""
    db = SessionLocal()
    try:
        project = Project(name="U-P1c 撤销测试")
        db.add(project)
        db.flush()
        batch = ImportBatch(
            project_id=project.id,
            file_name="undo.xlsx",
            status="imported",
            data_date=date(2026, 5, 22),
            is_frozen=frozen,
        )
        db.add(batch)
        db.flush()
        item = ProgressItem(
            project_id=project.id,
            batch_id=batch.id,
            task_code="T-100",
            task_name="桥架安装",
            actual_percent=30.0,
            planned_percent=50.0,
        )
        db.add(item)
        db.commit()
        return project.id, batch.id, item.id
    finally:
        db.close()


def test_undo_reverts_single_edit_and_clears_history() -> None:
    _project_id, _batch_id, item_id = _setup_progress_item()
    with TestClient(app) as client:
        # 改 actual_percent: 30 → 60
        put = client.put(
            f"/api/progress-items/{item_id}",
            json={"reason": "现场实测后修正", "actual_percent": 60.0},
        )
        assert put.status_code == 200, put.text
        assert put.json()["actual_percent"] == 60.0
        assert put.json()["is_manually_edited"] is True

        # 撤销
        undo = client.post(f"/api/progress-items/{item_id}/undo-last-edit")
        assert undo.status_code == 200, undo.text
        body = undo.json()
        assert body["actual_percent"] == 30.0
        # 撤销后没有其它历史 → is_manually_edited 必须清掉
        assert body["is_manually_edited"] is False

    # 数据库层校验:窗口内的历史条目已被删除,只剩 __undo__ 审计行
    db = SessionLocal()
    try:
        rows = db.execute(
            select(ProgressItemEditHistory).where(
                ProgressItemEditHistory.progress_item_id == item_id
            )
        ).scalars().all()
        # 应只剩 1 条 __undo__ 审计记录
        assert len(rows) == 1
        assert rows[0].field_name == "__undo__"
        assert "撤销操作" in (rows[0].reason or "")
    finally:
        db.close()


def test_undo_twice_reverts_two_separate_edits() -> None:
    _project_id, _batch_id, item_id = _setup_progress_item()
    with TestClient(app) as client:
        # 第一次改 actual_percent: 30 → 50
        client.put(
            f"/api/progress-items/{item_id}",
            json={"reason": "第一次修正", "actual_percent": 50.0},
        )
        # 第二次改 actual_percent: 50 → 80
        client.put(
            f"/api/progress-items/{item_id}",
            json={"reason": "第二次修正", "actual_percent": 80.0},
        )

        # 撤销 → 应回到 50
        first_undo = client.post(f"/api/progress-items/{item_id}/undo-last-edit")
        assert first_undo.status_code == 200, first_undo.text
        assert first_undo.json()["actual_percent"] == 50.0
        # 仍有更早的"第一次修正"历史 → is_manually_edited 不能清
        assert first_undo.json()["is_manually_edited"] is True

        # 再撤销一次 → 应回到 30
        second_undo = client.post(f"/api/progress-items/{item_id}/undo-last-edit")
        assert second_undo.status_code == 200, second_undo.text
        assert second_undo.json()["actual_percent"] == 30.0
        assert second_undo.json()["is_manually_edited"] is False


def test_undo_rejects_frozen_batch() -> None:
    _project_id, _batch_id, item_id = _setup_progress_item(frozen=True)
    # 冻结批次连 PUT 都拦,所以直接调 undo——应该被批次冻结检查挡住
    with TestClient(app) as client:
        resp = client.post(f"/api/progress-items/{item_id}/undo-last-edit")
        assert resp.status_code == 400
        assert "冻结" in resp.json()["detail"]


def test_undo_with_no_history_returns_400() -> None:
    _project_id, _batch_id, item_id = _setup_progress_item()
    with TestClient(app) as client:
        resp = client.post(f"/api/progress-items/{item_id}/undo-last-edit")
        assert resp.status_code == 400
        assert "撤销" in resp.json()["detail"]


def test_undo_on_missing_item_returns_404() -> None:
    with TestClient(app) as client:
        resp = client.post("/api/progress-items/999999/undo-last-edit")
        assert resp.status_code == 404


def test_undo_groups_by_edit_session_id_not_reason() -> None:
    """新数据按 edit_session_id 分组——即便两次 PUT 的 reason 字符串完全相同
    (例如批量改时填了同样的"现场实测"理由),撤销也必须只撤销最后一次,而不是把两次
    合并撤回去。这是旧的"按 reason 窗口"算法做不到的。"""
    _project_id, _batch_id, item_id = _setup_progress_item()
    with TestClient(app) as client:
        # 两次 PUT 用完全相同的 reason
        client.put(
            f"/api/progress-items/{item_id}",
            json={"reason": "现场实测", "actual_percent": 45.0},
        )
        client.put(
            f"/api/progress-items/{item_id}",
            json={"reason": "现场实测", "actual_percent": 70.0},
        )

        # 撤销一次只回退最近那次:70 → 45,而不是直接回到 30
        first = client.post(f"/api/progress-items/{item_id}/undo-last-edit")
        assert first.status_code == 200, first.text
        assert first.json()["actual_percent"] == 45.0

        # 再撤销一次回到 30
        second = client.post(f"/api/progress-items/{item_id}/undo-last-edit")
        assert second.status_code == 200, second.text
        assert second.json()["actual_percent"] == 30.0


def test_undo_legacy_rows_without_session_id_still_work() -> None:
    """老数据(edit_session_id=NULL)撤销端点回退到"reason + 2 秒窗口"近似算法。
    这是为了不破坏迁移前已存在的历史数据。"""
    _project_id, _batch_id, item_id = _setup_progress_item()
    # 手工模拟"老数据":直接写两条 edit_session_id=NULL 的历史,模拟迁移前的状态
    db = SessionLocal()
    try:
        item = db.get(ProgressItem, item_id)
        assert item is not None
        item.actual_percent = 88.0
        item.is_manually_edited = True
        item.manual_edit_reason = "手工模拟老数据"
        db.add(
            ProgressItemEditHistory(
                progress_item_id=item_id,
                field_name="actual_percent",
                old_value="30.0",
                new_value="88.0",
                reason="手工模拟老数据",
                edited_by="system",
                edit_session_id=None,
            )
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        resp = client.post(f"/api/progress-items/{item_id}/undo-last-edit")
        assert resp.status_code == 200, resp.text
        assert resp.json()["actual_percent"] == 30.0
        assert resp.json()["is_manually_edited"] is False
