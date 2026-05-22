from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.ai_call_log import AiCallLog
from app.models.ai_prompt_template import AiPromptTemplate
from app.models.baseline_plan import BaselinePlan
from app.models.calculation_profile import CalculationProfile
from app.models.import_batch import ImportBatch
from app.models.import_validation_issue import ImportValidationIssue
from app.models.mapping_field import MappingField
from app.models.mapping_template import MappingTemplate
from app.models.progress_item import ProgressItem
from app.models.progress_item_edit_history import ProgressItemEditHistory
from app.models.progress_task import ProgressTask
from app.models.project import Project
from app.models.raw_import_row import RawImportRow
from app.models.rectification_action_log import RectificationActionLog
from app.models.rectification_item import RectificationItem
from app.models.report_export_record import ReportExportRecord
from app.models.standard_dictionary import StandardDictionary
from app.models.warning_record import WarningRecord
from app.models.warning_rule import WarningRule


CONFIRM_TEXT = "确认删除项目"


def test_empty_project_can_be_force_deleted() -> None:
    with TestClient(app) as client:
        created = client.post("/api/projects", json={"name": "可强制删除空项目"})
        project_id = created.json()["id"]

        response = client.request("DELETE", f"/api/projects/{project_id}/force", json={"confirm_text": CONFIRM_TEXT})
        detail_response = client.get(f"/api/projects/{project_id}")

    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert response.json()["project_id"] == project_id
    assert response.json()["deleted_counts"]["import_batches"] == 0
    assert detail_response.status_code == 404
    assert detail_response.json()["detail"]["code"] == "PROJECT_NOT_FOUND"


def test_force_delete_rejects_wrong_confirm_text() -> None:
    with TestClient(app) as client:
        created = client.post("/api/projects", json={"name": "确认文字错误项目"})
        project_id = created.json()["id"]

        response = client.request("DELETE", f"/api/projects/{project_id}/force", json={"confirm_text": "删除"})
        detail_response = client.get(f"/api/projects/{project_id}")

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "DELETE_CONFIRM_MISMATCH"
    assert detail_response.status_code == 200


def test_project_with_related_data_can_be_force_deleted_and_returns_counts() -> None:
    project_id = _create_project_with_all_related_data()

    with TestClient(app) as client:
        response = client.request("DELETE", f"/api/projects/{project_id}/force", json={"confirm_text": CONFIRM_TEXT})
        detail_response = client.get(f"/api/projects/{project_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "项目及关联数据已删除。"
    assert data["deleted_counts"] == {
        "import_batches": 1,
        "progress_items": 1,
        "warnings": 1,
        "rectifications": 1,
        "reports": 1,
        "baselines": 1,
    }
    assert detail_response.status_code == 404

    db = SessionLocal()
    try:
        assert db.get(Project, project_id) is None
        assert db.query(ImportBatch).filter(ImportBatch.project_id == project_id).count() == 0
        assert db.query(ProgressTask).filter(ProgressTask.project_id == project_id).count() == 0
        assert db.query(ProgressItem).filter(ProgressItem.project_id == project_id).count() == 0
        assert db.query(WarningRecord).filter(WarningRecord.project_id == project_id).count() == 0
        assert db.query(WarningRule).filter(WarningRule.project_id == project_id).count() == 0
        assert db.query(RectificationItem).filter(RectificationItem.project_id == project_id).count() == 0
        assert db.query(RectificationActionLog).filter(RectificationActionLog.project_id == project_id).count() == 0
        assert db.query(ReportExportRecord).filter(ReportExportRecord.project_id == project_id).count() == 0
        assert db.query(BaselinePlan).filter(BaselinePlan.project_id == project_id).count() == 0
        assert db.query(CalculationProfile).filter(CalculationProfile.project_id == project_id).count() == 0
        assert db.query(MappingTemplate).filter(MappingTemplate.project_id == project_id).count() == 0
        assert db.query(StandardDictionary).filter(StandardDictionary.project_id == project_id).count() == 0
        assert db.query(AiCallLog).filter(AiCallLog.project_id == project_id).count() == 0
        assert db.query(AiPromptTemplate).filter(AiPromptTemplate.project_id == project_id).count() == 0
        assert db.query(ImportValidationIssue).count() == 0
        assert db.query(RawImportRow).count() == 0
        assert db.query(ProgressItemEditHistory).count() == 0
    finally:
        db.close()


def test_force_delete_project_a_does_not_affect_project_b_or_global_templates() -> None:
    project_a_id = _create_project_with_all_related_data("项目A")
    db = SessionLocal()
    try:
        project_b = Project(name="项目B")
        db.add(project_b)
        db.flush()
        batch_b = ImportBatch(project_id=project_b.id, file_name="b.csv")
        db.add(batch_b)
        global_template = MappingTemplate(project_id=None, name="全局模板", is_global=True)
        db.add(global_template)
        db.commit()
        project_b_id = project_b.id
        global_template_id = global_template.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.request("DELETE", f"/api/projects/{project_a_id}/force", json={"confirm_text": CONFIRM_TEXT})

    assert response.status_code == 200

    db = SessionLocal()
    try:
        assert db.get(Project, project_a_id) is None
        assert db.get(Project, project_b_id) is not None
        assert db.query(ImportBatch).filter(ImportBatch.project_id == project_b_id).count() == 1
        assert db.get(MappingTemplate, global_template_id) is not None
    finally:
        db.close()


def _create_project_with_all_related_data(project_name: str = "有数据项目") -> int:
    db = SessionLocal()
    try:
        project = Project(name=project_name)
        db.add(project)
        db.flush()

        baseline = BaselinePlan(project_id=project.id, name="基线")
        profile = CalculationProfile(project_id=project.id, name="口径")
        db.add_all([baseline, profile])
        db.flush()

        batch = ImportBatch(project_id=project.id, file_name="a.csv", status="published", baseline_plan_id=baseline.id, calculation_profile_id=profile.id)
        db.add(batch)
        db.flush()

        task = ProgressTask(project_id=project.id, task_name="桥架安装")
        db.add(task)
        db.flush()

        item = ProgressItem(project_id=project.id, batch_id=batch.id, task_id=task.id, baseline_plan_id=baseline.id, task_name="桥架安装")
        db.add(item)
        db.flush()

        rule = WarningRule(project_id=project.id, name="滞后规则", rule_type="delay")
        db.add(rule)
        db.flush()

        warning = WarningRecord(project_id=project.id, batch_id=batch.id, task_id=task.id, rule_id=rule.id, title="滞后")
        db.add(warning)
        db.flush()

        rectification = RectificationItem(
            project_id=project.id,
            batch_id=batch.id,
            progress_item_id=item.id,
            warning_record_id=warning.id,
            source_type="warning",
            task_name="桥架安装",
        )
        db.add(rectification)
        db.flush()

        template = MappingTemplate(project_id=project.id, name="项目模板")
        db.add(template)
        db.flush()

        db.add_all(
            [
                ProgressItemEditHistory(progress_item_id=item.id, field_name="actual_percent", old_value="10", new_value="20"),
                RectificationActionLog(rectification_item_id=rectification.id, project_id=project.id, action="create"),
                ReportExportRecord(project_id=project.id, batch_id=batch.id, report_type="overview"),
                MappingField(template_id=template.id, excel_column_name="工作内容", system_field_name="task_name"),
                ImportValidationIssue(batch_id=batch.id, level="warning", message="日期格式提示"),
                RawImportRow(batch_id=batch.id, row_index=1, raw_data="{}"),
                StandardDictionary(project_id=project.id, field_name="discipline", raw_value="电", standard_value="电气"),
                AiCallLog(project_id=project.id, batch_id=batch.id, mode="summary", source="test"),
                AiPromptTemplate(project_id=project.id, name="项目提示词", code="summary", prompt_template="test"),
            ]
        )
        db.commit()
        return project.id
    finally:
        db.close()
