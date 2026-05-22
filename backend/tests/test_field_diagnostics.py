from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.database import SessionLocal
from app.main import app
from app.models.import_batch import ImportBatch
from app.models.mapping_field import MappingField
from app.models.mapping_template import MappingTemplate
from app.models.progress_item import ProgressItem
from app.models.project import Project
from app.services.template_matcher import match_templates


def _seed_items(rows: list[ProgressItem]) -> tuple[int, int]:
    db = SessionLocal()
    try:
        project = Project(name="v4.3 field diagnostics")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="diag.xlsx", sheet_name="进度", status="published", data_date=date(2026, 5, 19))
        db.add(batch)
        db.flush()
        for row in rows:
            row.project_id = project.id
            row.batch_id = batch.id
        db.add_all(rows)
        db.commit()
        return project.id, batch.id
    finally:
        db.close()


def test_field_diagnostics_recommends_weighted_percent_when_weight_exists() -> None:
    _, batch_id = _seed_items([ProgressItem(task_name="A", actual_percent=50, weight=1), ProgressItem(task_name="B", actual_percent=80, weight=2)])
    with TestClient(app) as client:
        response = client.get(f"/api/imports/{batch_id}/field-diagnostics")
    assert response.status_code == 200
    assert response.json()["recommended_calculation_method"] == "weighted_percent"


def test_field_diagnostics_mixed_units_does_not_recommend_quantity_percent() -> None:
    _, batch_id = _seed_items([
        ProgressItem(task_name="A", total_quantity=100, cumulative_quantity=50, unit="米"),
        ProgressItem(task_name="B", total_quantity=10, cumulative_quantity=5, unit="个"),
    ])
    with TestClient(app) as client:
        payload = client.get(f"/api/imports/{batch_id}/field-diagnostics").json()
    assert payload["recommended_calculation_method"] != "quantity_percent"
    quantity = next(item for item in payload["available_calculation_methods"] if item["code"] == "quantity_percent")
    assert "多种单位" in quantity["warning"]


def test_field_diagnostics_same_unit_recommends_quantity_percent() -> None:
    _, batch_id = _seed_items([
        ProgressItem(task_name="A", total_quantity=100, cumulative_quantity=50, unit="米"),
        ProgressItem(task_name="B", total_quantity=200, cumulative_quantity=100, unit="米"),
    ])
    with TestClient(app) as client:
        payload = client.get(f"/api/imports/{batch_id}/field-diagnostics").json()
    assert payload["recommended_calculation_method"] == "quantity_percent"


def test_field_diagnostics_missing_plan_dates_and_dimensions_report_impacts() -> None:
    _, batch_id = _seed_items([ProgressItem(task_name="A", actual_percent=30)])
    with TestClient(app) as client:
        payload = client.get(f"/api/imports/{batch_id}/field-diagnostics").json()
    impacts = {item["field"]: item["impact"] for item in payload["field_impacts"]}
    assert "planned_start_date" in impacts
    assert payload["dashboard_capabilities"]["building_view"]["available"] is False
    assert payload["dashboard_capabilities"]["floor_heatmap"]["available"] is False


def test_field_diagnostics_endpoint_returns_200_for_parsed_batch(tmp_path: Path) -> None:
    path = tmp_path / "diag.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "进度"
    sheet.append(["工作内容", "实际完成率"])
    sheet.append(["桥架安装", "50%"])
    workbook.save(path)

    db = SessionLocal()
    try:
        project = Project(name="parsed diagnostics")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="diag.xlsx", file_path=str(path), sheet_name="进度", header_row_index=1, data_start_row_index=2, status="parsed")
        db.add(batch)
        db.commit()
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(f"/api/imports/{batch_id}/field-diagnostics")
    assert response.status_code == 200
    assert response.json()["field_mapping_quality"]["recognized_count"] >= 2


def test_template_matcher_returns_match_breakdown() -> None:
    db = SessionLocal()
    try:
        project = Project(name="template match diagnostics")
        db.add(project)
        db.flush()
        template = MappingTemplate(project_id=project.id, name="模板", field_structure='{"sheet_name":"进度"}', is_active=True)
        db.add(template)
        db.flush()
        db.add_all([
            MappingField(template_id=template.id, excel_column_name="工作内容", system_field_name="task_name", field_type="text", sort_order=1),
            MappingField(template_id=template.id, excel_column_name="楼栋", system_field_name="building", field_type="text", sort_order=2),
            MappingField(template_id=template.id, excel_column_name="实际完成率", system_field_name="actual_percent", field_type="percent", sort_order=3),
        ])
        db.commit()
        matches = match_templates(db, project.id, ["工作内容", "实际完成率"])
        assert matches
        assert matches[0].hit_field_count == 2
        assert matches[0].missing_field_count == 1
        assert "楼栋" in matches[0].possible_mismatch_fields
    finally:
        db.close()
