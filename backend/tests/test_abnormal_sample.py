from pathlib import Path

from app.schemas.mapping import FieldMapping
from app.services.excel_parser import parse_rows
from app.services.import_validator import validate_import_rows


SAMPLE_DIR = Path(__file__).resolve().parents[2] / "samples"


def test_abnormal_sample_reports_expected_validation_issues() -> None:
    rows = parse_rows(str(SAMPLE_DIR / "sample_progress_abnormal.csv"), "CSV", 1, 2, False, None)
    mappings = [
        FieldMapping(excel_column_name="楼栋", system_field_name="building"),
        FieldMapping(excel_column_name="楼层", system_field_name="floor"),
        FieldMapping(excel_column_name="专业", system_field_name="discipline"),
        FieldMapping(excel_column_name="工作内容", system_field_name="task_name"),
        FieldMapping(excel_column_name="单位", system_field_name="unit"),
        FieldMapping(excel_column_name="总工程量", system_field_name="total_quantity"),
        FieldMapping(excel_column_name="累计完成量", system_field_name="cumulative_quantity"),
        FieldMapping(excel_column_name="计划完成率", system_field_name="planned_percent"),
        FieldMapping(excel_column_name="实际完成率", system_field_name="actual_percent"),
        FieldMapping(excel_column_name="计划开始", system_field_name="planned_start_date"),
        FieldMapping(excel_column_name="计划完成", system_field_name="planned_finish_date"),
    ]

    issues, normalized_rows = validate_import_rows(rows, mappings)
    codes = {issue.code for issue in issues}

    assert normalized_rows[0]["floor"] == "B1层"
    assert normalized_rows[1]["floor"] == "B1层"
    assert "negative_quantity" in codes
    assert "actual_exceeds_total" in codes
    assert "percent_out_of_range" in codes
    assert "INVALID_DATE" in codes
    assert "SUMMARY_ROW_SKIPPED" in codes
    assert "task_name_empty" not in codes
    assert normalized_rows[1]["__skip_import"] is True
    assert normalized_rows[2]["__skip_import"] is True
