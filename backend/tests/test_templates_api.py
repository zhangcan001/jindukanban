from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.calculation_profile import CalculationProfile
from app.models.mapping_field import MappingField
from app.models.mapping_template import MappingTemplate
from app.models.warning_rule import WarningRule
from app.services.template_matcher import match_templates


def test_project_template_list_and_create_project_applies_defaults() -> None:
    with TestClient(app) as client:
        templates_response = client.get("/api/templates/project-templates")
        assert templates_response.status_code == 200
        templates = templates_response.json()
        assert any(template["name"] == "机电安装项目模板" for template in templates)
        template_id = next(template["id"] for template in templates if template["code"] == "mep-installation")

        project_response = client.post(
            "/api/projects",
            json={"name": "模板项目", "template_id": template_id},
        )

    assert project_response.status_code == 201
    project = project_response.json()
    assert project["template_id"] == template_id
    assert project["default_calculation_profile_id"] is not None
    assert project["dashboard_config"] is not None
    assert project["report_config"] is not None

    db = SessionLocal()
    try:
        profile_count = db.query(CalculationProfile).filter(CalculationProfile.project_id == project["id"]).count()
        rules = db.query(WarningRule).filter(WarningRule.project_id == project["id"]).all()
    finally:
        db.close()
    assert profile_count == 1
    assert len(rules) >= 3
    assert all(rule.rule_type != "low_data_quality" for rule in rules)


def test_mapping_template_management_and_weighted_match() -> None:
    db = SessionLocal()
    try:
        template = MappingTemplate(project_id=None, name="机电周进度模板", is_global=True, is_active=True)
        db.add(template)
        db.flush()
        db.add_all(
            [
                MappingField(template_id=template.id, excel_column_name="施工内容", system_field_name="task_name", field_type="text", sort_order=1),
                MappingField(template_id=template.id, excel_column_name="实际进度", system_field_name="actual_percent", field_type="percent", sort_order=2),
                MappingField(template_id=template.id, excel_column_name="计划进度", system_field_name="planned_percent", field_type="percent", sort_order=3),
                MappingField(template_id=template.id, excel_column_name="楼栋", system_field_name="building", field_type="text", sort_order=4),
            ]
        )
        db.commit()
        template_id = template.id
    finally:
        db.close()

    with TestClient(app) as client:
        list_response = client.get("/api/templates/mapping-templates")
        update_response = client.put(f"/api/templates/mapping-templates/{template_id}", json={"name": "机电模板重命名"})

    assert list_response.status_code == 200
    assert any(template["id"] == template_id for template in list_response.json())
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "机电模板重命名"


def test_builtin_project_template_can_be_copied_but_not_deleted() -> None:
    with TestClient(app) as client:
        templates = client.get("/api/templates/project-templates").json()
        builtin_id = next(template["id"] for template in templates if template["is_builtin"])
        copy_response = client.post(f"/api/templates/project-templates/{builtin_id}/copy")
        delete_builtin_response = client.delete(f"/api/templates/project-templates/{builtin_id}")

    assert copy_response.status_code == 201
    assert copy_response.json()["is_builtin"] is False
    assert delete_builtin_response.status_code == 400


def test_project_type_mapping_template_is_recommended_across_projects() -> None:
    with TestClient(app) as client:
        template_id = next(
            template["id"]
            for template in client.get("/api/templates/project-templates").json()
            if template["code"] == "mep-installation"
        )
        first = client.post("/api/projects", json={"name": "模板推荐来源项目", "template_id": template_id}).json()
        second = client.post("/api/projects", json={"name": "模板推荐目标项目", "template_id": template_id}).json()

    db = SessionLocal()
    try:
        mapping_template = MappingTemplate(
            project_id=first["id"],
            project_type=first["project_type"],
            name="跨项目机电模板",
            is_global=False,
            is_active=True,
        )
        db.add(mapping_template)
        db.flush()
        db.add_all(
            [
                MappingField(template_id=mapping_template.id, excel_column_name="施工内容", system_field_name="task_name", field_type="text"),
                MappingField(template_id=mapping_template.id, excel_column_name="实际完成情况", system_field_name="actual_percent", field_type="percent"),
                MappingField(template_id=mapping_template.id, excel_column_name="楼栋", system_field_name="building", field_type="text"),
            ]
        )
        db.commit()

        matches = match_templates(db, second["id"], ["楼栋", "施工内容", "实际完成情况"])
    finally:
        db.close()

    assert matches
    assert matches[0].name == "跨项目机电模板"
