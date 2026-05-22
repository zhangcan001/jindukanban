from app.database import SessionLocal
from app.schemas.mapping import FieldMapping
from app.schemas.validation import ImportValidationIssueRead
from app.services.data_quality_service import calculate_data_quality_score


MAPPINGS = [
    FieldMapping(excel_column_name="工作内容", system_field_name="task_name"),
    FieldMapping(excel_column_name="楼栋", system_field_name="building"),
    FieldMapping(excel_column_name="楼层", system_field_name="floor"),
    FieldMapping(excel_column_name="专业", system_field_name="discipline"),
    FieldMapping(excel_column_name="单位", system_field_name="unit"),
    FieldMapping(excel_column_name="总工程量", system_field_name="total_quantity"),
    FieldMapping(excel_column_name="计划完成率", system_field_name="planned_percent"),
]


def test_data_quality_score_is_higher_for_complete_valid_rows() -> None:
    db = SessionLocal()
    try:
        good_rows = [
            {
                "task_name": "桥架安装",
                "building": "1号楼",
                "floor": "1层",
                "discipline": "电气",
                "unit": "米",
                "total_quantity": 100,
                "planned_percent": 80,
            }
        ]
        bad_rows = [{"task_name": "", "building": "", "unit": "", "total_quantity": None}]
        issues = [ImportValidationIssueRead(row_index=1, level="error", code="task_name_empty", message="任务名称为空")]

        good_score = calculate_data_quality_score(db, 1, good_rows, MAPPINGS, [])
        bad_score = calculate_data_quality_score(db, 1, bad_rows, MAPPINGS, issues)

        assert good_score.data_quality_score > bad_score.data_quality_score
        assert good_score.data_quality_score >= 70
    finally:
        db.close()
