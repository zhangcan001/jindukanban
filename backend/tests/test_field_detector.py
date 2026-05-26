from app.services.field_detector import detect_column
from app.schemas.mapping import FieldMapping
from app.services.field_mapping_validator import validate_field_mappings


def test_field_detector_uses_specific_rules_before_fallbacks() -> None:
    cases = {
        "WBS编码": "wbs_code",
        "任务信息_WBS编码": "wbs_code",
        "任务编码": "task_code",
        "清单编码": "task_code",
        "计划完成率": "planned_percent",
        "实际完成率": "actual_percent",
        "本周完成量": "period_quantity",
        "累计完成量": "cumulative_quantity",
        "进度百分比": "actual_percent",
        "工作内容": "task_name",
        "施工内容": "task_name",
        "施工项": "task_name",
        "工序内容": "task_name",
        "实际完成情况": "actual_percent",
        "完成情况": "actual_percent",
        "楼层": "floor",
        "层": "floor",
        "所在楼层": "floor",
        "施工楼层": "floor",
        "楼层/区域": "floor",
        "单位": "unit",
        "计量单位": "unit",
        "工程量单位": "unit",
        "数量单位": "unit",
    }

    for column, expected in cases.items():
        assert detect_column(column)["recommended_field"] == expected

    assert detect_column("楼栋")["recommended_field"] == "building"


def test_field_detector_maps_generic_completion_rate_to_actual_percent() -> None:
    assert detect_column("完成率")["recommended_field"] == "actual_percent"


def test_field_detector_maps_real_progress_aliases_before_date_fields() -> None:
    assert detect_column("实际完成情况")["recommended_field"] == "actual_percent"
    assert detect_column("完成进度")["recommended_field"] == "actual_percent"
    assert detect_column("计划完成进度")["recommended_field"] == "planned_percent"
    assert detect_column("合同量")["recommended_field"] == "total_quantity"


def test_field_detector_normalizes_units_and_newlines() -> None:
    assert detect_column("实际\n完成率（%）")["recommended_field"] == "actual_percent"
    assert detect_column("计划 完成 比例")["recommended_field"] == "planned_percent"


def test_field_detector_uses_sample_values_for_ambiguous_headers() -> None:
    detected = detect_column("当前情况", ["10%", "20%", "35%"])

    assert detected["recommended_field"] == "actual_percent"
    assert detected["field_type"] == "percent"
    assert detected["needs_review"] is False


def test_field_detector_marks_ambiguous_sample_inference_for_review() -> None:
    detected = detect_column("比例", ["0.1", "0.2", "0.35"])

    assert detected["recommended_field"] is None
    assert detected["field_type"] == "percent"


def test_field_detector_does_not_map_responsibility_units_to_quantity_unit() -> None:
    for column in ["建设单位", "监理单位", "班组单位"]:
        detected = detect_column(column)
        assert detected["recommended_field"] != "unit"
        assert detected["recommended_field"] is None
        assert detected["field_type"] == "unknown"
    for column in ["施工单位", "分包单位", "责任单位", "单位名称", "承包单位"]:
        detected = detect_column(column)
        assert detected["recommended_field"] == "construction_unit"
        assert detected["field_type"] == "text"


def test_unit_and_construction_unit_do_not_trigger_duplicate_system_field() -> None:
    unit = detect_column("单位")
    construction_unit = detect_column("施工单位")
    mappings = [
        FieldMapping(
            excel_column_name="单位",
            recommended_field=unit["recommended_field"],
            system_field_name=unit["recommended_field"],
            field_type=unit["field_type"] or "unknown",
            save_to_extra=unit["recommended_field"] is None,
        ),
        FieldMapping(
            excel_column_name="施工单位",
            recommended_field=construction_unit["recommended_field"],
            system_field_name=construction_unit["recommended_field"],
            field_type=construction_unit["field_type"] or "unknown",
            save_to_extra=construction_unit["recommended_field"] is None,
        ),
    ]

    issues = validate_field_mappings(mappings)

    assert construction_unit["recommended_field"] == "construction_unit"
    assert mappings[1].save_to_extra is False
    assert not any(issue.code == "duplicate_system_field" for issue in issues)
