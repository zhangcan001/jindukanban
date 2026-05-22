"""D-P0c: 重复调用 /validate 不应让 import_validation_issue 累积重复行。

旧 bug 场景:用户在导入向导里反复点"重新校验",每次都把同样的"日期格式可能不正确"
warning 写一份到表里——再去看校验报告就会看到 N 份重复 issue,而且 issue_code_counts
也会按重复行数膨胀。
"""
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models.import_validation_issue import ImportValidationIssue


FIELD_MAPPINGS = [
    {"excel_column_name": "工作内容", "system_field_name": "task_name", "field_type": "text", "is_dimension": True},
    {"excel_column_name": "楼栋", "system_field_name": "building", "field_type": "text", "is_dimension": True},
    {"excel_column_name": "计划完成率", "system_field_name": "planned_percent", "field_type": "percent", "is_metric": True},
    {"excel_column_name": "实际完成率", "system_field_name": "actual_percent", "field_type": "percent", "is_metric": True},
    {"excel_column_name": "计划开始", "system_field_name": "planned_start_date", "field_type": "date"},
    {"excel_column_name": "计划完成", "system_field_name": "planned_finish_date", "field_type": "date"},
]


def _build_warning_xlsx(tmp_path: Path) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["工作内容", "楼栋", "计划完成率", "实际完成率", "计划开始", "计划完成"])
    # 两行都有"日期格式可能不正确"的 warning——但每次 validate 应该只各落 1 条
    sheet.append(["任务A", "1#楼", "50%", "30%", "abc", "def"])
    sheet.append(["任务B", "1#楼", "60%", "40%", "xyz", "qqq"])
    path = tmp_path / "warn.xlsx"
    workbook.save(path)
    return path


def test_revalidating_does_not_accumulate_duplicate_issues(tmp_path: Path) -> None:
    file_path = _build_warning_xlsx(tmp_path)
    with TestClient(app) as client:
        project_id = client.post("/api/projects", json={"name": "D-P0c 去重测试"}).json()["id"]
        with file_path.open("rb") as f:
            upload = client.post(
                f"/api/projects/{project_id}/imports/upload",
                data={"data_date": "2026-05-22"},
                files={"file": ("warn.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
        batch_id = upload.json()["batch"]["id"]
        sheet_name = upload.json()["sheets"][0]
        client.post(
            f"/api/imports/{batch_id}/parse",
            json={"sheet_name": sheet_name, "header_row_index": 1, "data_start_row_index": 2},
        )
        # 连续校验 3 次——模拟用户反复点"重新校验"
        for _ in range(3):
            r = client.post(f"/api/imports/{batch_id}/validate", json={"field_mappings": FIELD_MAPPINGS})
            assert r.status_code == 200

    db = SessionLocal()
    try:
        rows = db.execute(
            select(ImportValidationIssue).where(ImportValidationIssue.batch_id == batch_id)
        ).scalars().all()
        # 用 (row_index, column_name, code) 做唯一性检查——每次 validate 后,这个集合
        # 的大小应该等于该批次产生的 distinct issue 数
        distinct_keys = {(row.row_index, row.column_name, row.code) for row in rows}
        # 没有重复行
        assert len(rows) == len(distinct_keys), (
            f"validate 重跑后 import_validation_issue 累积了重复:"
            f" total={len(rows)} distinct={len(distinct_keys)}"
        )
    finally:
        db.close()
