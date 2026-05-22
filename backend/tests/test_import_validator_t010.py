from app.schemas.mapping import FieldMapping
from app.schemas.validation import summarize_issue_codes
from app.services.import_validator import should_skip_import, validate_import_rows


def test_large_real_progress_batch_is_not_treated_as_abnormal() -> None:
    rows = [
        {
            "楼栋": f"A{index % 10}",
            "楼层": f"{index % 30 + 1}层",
            "专业": "机电",
            "施工内容": f"机电任务{index}",
            "实际完成情况": "未开始" if index % 2 else 0.1,
        }
        for index in range(637)
    ]
    mappings = [
        FieldMapping(excel_column_name="楼栋", system_field_name="building"),
        FieldMapping(excel_column_name="楼层", system_field_name="floor"),
        FieldMapping(excel_column_name="专业", system_field_name="discipline"),
        FieldMapping(excel_column_name="施工内容", system_field_name="task_name"),
        FieldMapping(excel_column_name="实际完成情况", system_field_name="actual_percent", field_type="percent"),
    ]

    issues, normalized_rows = validate_import_rows(rows, mappings)

    assert len(normalized_rows) == 637
    assert not any(should_skip_import(row) for row in normalized_rows)
    assert {issue.code for issue in issues} == {
        "planned_start_date_missing",
        "planned_finish_date_missing",
        "total_quantity_missing",
        "cumulative_quantity_missing",
    }
    assert all(issue.level == "warning" for issue in issues)
    assert normalized_rows[0]["actual_percent"] == 0.1
    assert normalized_rows[1]["actual_percent"] == "未开始"


def test_validation_issue_codes_are_summarized_by_type() -> None:
    rows = [{"施工内容": "A", "实际完成情况": "abc"}, {"施工内容": "", "实际完成情况": "abc"}]
    mappings = [
        FieldMapping(excel_column_name="施工内容", system_field_name="task_name"),
        FieldMapping(excel_column_name="实际完成情况", system_field_name="actual_percent", field_type="percent"),
    ]

    issues, _ = validate_import_rows(rows, mappings)
    counts = {(item.code, item.level): item.count for item in summarize_issue_codes(issues)}

    assert counts[("invalid_percent", "error")] == 2
    assert counts[("task_name_empty", "error")] == 1
