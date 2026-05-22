from app.schemas.mapping import FieldMapping
from app.services.import_validator import is_summary_row, parse_percent, validate_import_rows


def test_validate_import_rows_normalizes_values_and_reports_errors() -> None:
    rows = [
        {"楼层": "负一层", "专业": "给排水", "工作内容": "给水管安装", "总工程量": "120", "累计完成量": "88"},
        {"楼层": "地下1层", "专业": "电气", "工作内容": "", "总工程量": "-100", "累计完成量": "50"},
    ]
    mappings = [
        FieldMapping(excel_column_name="楼层", system_field_name="floor"),
        FieldMapping(excel_column_name="专业", system_field_name="discipline"),
        FieldMapping(excel_column_name="工作内容", system_field_name="task_name"),
        FieldMapping(excel_column_name="总工程量", system_field_name="total_quantity"),
        FieldMapping(excel_column_name="累计完成量", system_field_name="cumulative_quantity"),
    ]

    issues, normalized_rows = validate_import_rows(rows, mappings)

    assert normalized_rows[0]["floor"] == "B1层"
    assert normalized_rows[0]["discipline"] == "给排水"
    assert {issue.code for issue in issues} >= {"negative_quantity", "task_name_empty"}


def test_percent_values_are_normalized_during_validation_and_warn_when_out_of_range() -> None:
    rows = [
        {"工作内容": "桥架安装", "实际完成率": "0.58"},
        {"工作内容": "风管安装", "实际完成率": "120%"},
        {"工作内容": "喷淋管安装", "实际完成率": "abc"},
    ]
    mappings = [
        FieldMapping(excel_column_name="工作内容", system_field_name="task_name"),
        FieldMapping(excel_column_name="实际完成率", system_field_name="actual_percent"),
    ]

    issues, _ = validate_import_rows(rows, mappings)

    assert parse_percent(0.58) == 58.0
    assert parse_percent("0.58") == 58.0
    assert parse_percent(58) == 58.0
    assert parse_percent("58") == 58.0
    assert parse_percent("58%") == 58.0
    assert parse_percent("not-a-percent") is None
    assert any(issue.code == "percent_out_of_range" and issue.level == "warning" for issue in issues)
    assert any(issue.code == "invalid_percent" and issue.level == "error" for issue in issues)


def test_summary_rows_are_marked_for_skip_without_task_name_error() -> None:
    rows = [
        {"工作内容": "合计", "专业": "", "总工程量": "100"},
        {"工作内容": "", "专业": "", "总工程量": "100", "第一列": "合计"},
        {"工作内容": "小计", "专业": "", "总工程量": "100"},
        {"工作内容": "总计", "专业": "", "总工程量": "100"},
        {"工作内容": "汇总", "专业": "", "总工程量": "100"},
        {"工作内容": "合 计", "专业": "", "总工程量": "100"},
        {"工作内容": "专业小计", "专业": "", "总工程量": "100"},
    ]
    mappings = [
        FieldMapping(excel_column_name="第一列", system_field_name="remark"),
        FieldMapping(excel_column_name="工作内容", system_field_name="task_name"),
        FieldMapping(excel_column_name="专业", system_field_name="discipline"),
        FieldMapping(excel_column_name="总工程量", system_field_name="total_quantity"),
    ]

    issues, normalized_rows = validate_import_rows(rows, mappings)

    assert all(row["__skip_import"] is True for row in normalized_rows)
    assert sum(1 for issue in issues if issue.code == "SUMMARY_ROW_SKIPPED") == len(rows)
    assert not any(issue.code == "task_name_empty" for issue in issues)


def test_summary_detector_does_not_skip_normal_task_names() -> None:
    assert not is_summary_row(
        {"工作内容": "配电箱安装", "楼栋": "1号楼", "楼层": "1层", "专业": "电气"},
        {"task_name": "配电箱安装", "building": "1号楼", "floor": "1层", "discipline": "电气"},
    )
    assert not is_summary_row(
        {"工作内容": "合计箱安装", "楼栋": "1号楼", "楼层": "1层", "专业": "电气"},
        {"task_name": "合计箱安装", "building": "1号楼", "floor": "1层", "discipline": "电气"},
    )


def test_valid_date_formats_do_not_report_invalid_date() -> None:
    rows = [
        {"工作内容": "桥架安装", "计划开始": "2026-05-01", "计划完成": "2026-05-30"},
        {"工作内容": "电缆敷设", "计划开始": "2026/05/02", "计划完成": "2026/05/31"},
        {"工作内容": "风管安装", "计划开始": "2026.05.03", "计划完成": "2026.06.01"},
        {"工作内容": "给水管安装", "计划开始": "2026年5月4日", "计划完成": "2026年6月2日"},
        {"工作内容": "喷淋管安装", "计划开始": "2026-05-01 00:00:00", "计划完成": ""},
        {"工作内容": "支架安装", "计划开始": "--", "计划完成": "/"},
    ]
    mappings = [
        FieldMapping(excel_column_name="工作内容", system_field_name="task_name"),
        FieldMapping(excel_column_name="计划开始", system_field_name="planned_start_date"),
        FieldMapping(excel_column_name="计划完成", system_field_name="planned_finish_date"),
    ]

    issues, _ = validate_import_rows(rows, mappings)

    assert not any(issue.code == "INVALID_DATE" for issue in issues)


def test_invalid_date_values_report_invalid_date_with_original_value() -> None:
    rows = [
        {"工作内容": "桥架安装", "计划开始": "2026-05-01", "计划完成": "日期错误"},
        {"工作内容": "电缆敷设", "计划开始": "2026/13/01", "计划完成": "2026/05/31"},
        {"工作内容": "风管安装", "计划开始": "2026-99-99", "计划完成": "2026/05/31"},
    ]
    mappings = [
        FieldMapping(excel_column_name="工作内容", system_field_name="task_name"),
        FieldMapping(excel_column_name="计划开始", system_field_name="planned_start_date"),
        FieldMapping(excel_column_name="计划完成", system_field_name="planned_finish_date"),
    ]

    issues, _ = validate_import_rows(rows, mappings)
    invalid_date_issues = [issue for issue in issues if issue.code == "INVALID_DATE"]

    assert len(invalid_date_issues) == 3
    assert invalid_date_issues[0].column_name == "计划完成"
    assert "日期错误" in invalid_date_issues[0].message


def test_non_date_fields_do_not_run_date_validation() -> None:
    rows = [{"工作内容": "桥架安装", "备注日期": "日期错误"}]
    mappings = [
        FieldMapping(excel_column_name="工作内容", system_field_name="task_name"),
        FieldMapping(excel_column_name="备注日期", system_field_name="remark"),
    ]

    issues, _ = validate_import_rows(rows, mappings)

    assert not any(issue.code == "INVALID_DATE" for issue in issues)
