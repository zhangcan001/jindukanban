"""D-P0a: 验证同批次 identity_key 唯一约束 + 导入去重行为。

场景：一份 Excel 里出现两行 task_code 完全相同的数据——不论是用户复制粘贴出错,
还是上游报表生成时的 bug——导入后只应落 1 条 ProgressItem,并在 issues 里以 warning
方式提示用户"第 N 行被去重"。
"""
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.main import app
from app.models.import_batch import ImportBatch
from app.models.progress_item import ProgressItem
from app.models.project import Project


FIELD_MAPPINGS = [
    {"excel_column_name": "任务编码", "system_field_name": "task_code", "field_type": "text", "is_dimension": True},
    {"excel_column_name": "工作内容", "system_field_name": "task_name", "field_type": "text", "is_dimension": True},
    {"excel_column_name": "楼栋", "system_field_name": "building", "field_type": "text", "is_dimension": True},
    {"excel_column_name": "楼层", "system_field_name": "floor", "field_type": "text", "is_dimension": True},
    {"excel_column_name": "专业", "system_field_name": "discipline", "field_type": "text", "is_dimension": True},
    {"excel_column_name": "计划完成率", "system_field_name": "planned_percent", "field_type": "percent", "is_metric": True},
    {"excel_column_name": "实际完成率", "system_field_name": "actual_percent", "field_type": "percent", "is_metric": True},
]


def _build_duplicate_xlsx(tmp_path: Path) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["任务编码", "工作内容", "楼栋", "楼层", "专业", "计划完成率", "实际完成率"])
    # 两行 task_code 相同——会生成同样的 identity_key
    sheet.append(["T-001", "桥架安装", "1#楼", "1F", "电气", "50%", "30%"])
    sheet.append(["T-001", "桥架安装(重复行)", "1#楼", "1F", "电气", "50%", "35%"])
    # 一行不同 task_code,正常导入
    sheet.append(["T-002", "管道安装", "1#楼", "2F", "给排水", "60%", "55%"])
    path = tmp_path / "dup.xlsx"
    workbook.save(path)
    return path


def test_duplicate_identity_key_within_batch_is_skipped(tmp_path: Path) -> None:
    file_path = _build_duplicate_xlsx(tmp_path)
    with TestClient(app) as client:
        project_id = client.post("/api/projects", json={"name": "D-P0a 去重测试"}).json()["id"]
        with file_path.open("rb") as f:
            upload = client.post(
                f"/api/projects/{project_id}/imports/upload",
                data={"data_date": "2026-05-22"},
                files={"file": ("dup.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
        assert upload.status_code == 200, upload.text
        batch_id = upload.json()["batch"]["id"]
        sheet_name = upload.json()["sheets"][0]
        client.post(
            f"/api/imports/{batch_id}/parse",
            json={"sheet_name": sheet_name, "header_row_index": 1, "data_start_row_index": 2},
        )
        confirm = client.post(
            f"/api/imports/{batch_id}/confirm",
            json={"import_strategy": "new_batch", "field_mappings": FIELD_MAPPINGS},
        )
    assert confirm.status_code == 200, confirm.text
    payload = confirm.json()
    # 3 行原始数据 → 应只导入 2 条 ProgressItem(1 条被去重)
    assert payload["imported_count"] == 2
    assert payload["skipped_count"] >= 1
    # warning 里应该看到 DUPLICATE_IDENTITY_KEY
    codes = [issue["code"] for issue in payload["issues"]]
    assert "DUPLICATE_IDENTITY_KEY" in codes

    # 数据库层面校验:同 batch 下 task_code=T-001 的 ProgressItem 只有 1 条
    db = SessionLocal()
    try:
        items = db.execute(
            select(ProgressItem).where(ProgressItem.batch_id == batch_id, ProgressItem.task_code == "T-001")
        ).scalars().all()
        assert len(items) == 1
    finally:
        db.close()


def test_unique_constraint_blocks_direct_duplicate_insert() -> None:
    """直接 ORM 层校验:绕过 confirm 流程,手动插两条同 identity_key,第二条应被唯一索引拒绝。"""
    db = SessionLocal()
    try:
        project = Project(name="D-P0a 唯一索引验证")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="x.xlsx", status="imported")
        db.add(batch)
        db.flush()
        db.add(
            ProgressItem(
                project_id=project.id,
                batch_id=batch.id,
                identity_key="dup-key-001",
                task_name="任务A",
            )
        )
        db.commit()

        db.add(
            ProgressItem(
                project_id=project.id,
                batch_id=batch.id,
                identity_key="dup-key-001",
                task_name="任务A(重复)",
            )
        )
        raised = False
        try:
            db.commit()
        except IntegrityError:
            raised = True
            db.rollback()
        assert raised, "同批次重复 identity_key 应触发 IntegrityError"
    finally:
        db.close()


def test_empty_identity_key_does_not_trigger_unique_constraint() -> None:
    """identity_key 为空/NULL 的兜底行不参与唯一约束——它们的'身份'本就不可靠,不应被互相阻塞。"""
    db = SessionLocal()
    try:
        project = Project(name="D-P0a 空 identity_key 验证")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="x.xlsx", status="imported")
        db.add(batch)
        db.flush()
        db.add(ProgressItem(project_id=project.id, batch_id=batch.id, identity_key=None, task_name="无身份A"))
        db.add(ProgressItem(project_id=project.id, batch_id=batch.id, identity_key="", task_name="无身份B"))
        db.add(ProgressItem(project_id=project.id, batch_id=batch.id, identity_key="", task_name="无身份C"))
        db.commit()  # 不应抛 IntegrityError
        rows = db.execute(
            select(ProgressItem).where(ProgressItem.batch_id == batch.id)
        ).scalars().all()
        assert len(rows) == 3
    finally:
        db.close()
