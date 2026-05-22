from app.database import SessionLocal
from app.models.mapping_field import MappingField
from app.models.mapping_template import MappingTemplate
from app.models.project import Project
from app.services.template_matcher import compute_header_hash, match_templates


def test_match_templates_returns_matching_template_fields() -> None:
    db = SessionLocal()
    try:
        project = Project(name="模板匹配测试")
        db.add(project)
        db.flush()
        template = MappingTemplate(project_id=project.id, name="标准模板")
        db.add(template)
        db.flush()
        db.add_all(
            [
                MappingField(template_id=template.id, excel_column_name="WBS编码", system_field_name="wbs_code", field_type="text"),
                MappingField(template_id=template.id, excel_column_name="工作内容", system_field_name="task_name", field_type="text"),
                MappingField(template_id=template.id, excel_column_name="实际完成率", system_field_name="actual_percent", field_type="percent"),
            ]
        )
        db.commit()

        matches = match_templates(db, project.id, ["WBS编码", "工作内容", "实际完成率"])

        assert len(matches) == 1
        assert matches[0].name == "标准模板"
        assert matches[0].match_score == 1
        assert {field.system_field_name for field in matches[0].fields} >= {"wbs_code", "task_name", "actual_percent"}
    finally:
        db.close()


def test_compute_header_hash_normalizes_whitespace_and_case() -> None:
    """同样的列名，大小写/空白差异不影响指纹。"""
    h1 = compute_header_hash(["WBS编码", "工作内容", "实际完成率"])
    h2 = compute_header_hash([" WBS编码 ", "工作内容", "实际完成率"])
    assert h1 == h2
    assert h1 != ""


def test_compute_header_hash_is_order_sensitive() -> None:
    """列顺序变了应当视为不同布局。"""
    h1 = compute_header_hash(["A", "B", "C"])
    h2 = compute_header_hash(["A", "C", "B"])
    assert h1 != h2


def test_compute_header_hash_ignores_blank_columns() -> None:
    assert compute_header_hash(["", "  ", None] ) == ""  # type: ignore[list-item]


def test_match_templates_marks_exact_match_when_header_hash_matches() -> None:
    db = SessionLocal()
    try:
        project = Project(name="一键复用测试")
        db.add(project)
        db.flush()
        columns = ["WBS编码", "工作内容", "实际完成率"]
        template = MappingTemplate(
            project_id=project.id,
            name="精确模板",
            sheet_name="进度明细",
            header_hash=compute_header_hash(columns),
        )
        db.add(template)
        db.flush()
        db.add_all(
            [
                MappingField(template_id=template.id, excel_column_name="WBS编码", system_field_name="wbs_code", field_type="text"),
                MappingField(template_id=template.id, excel_column_name="工作内容", system_field_name="task_name", field_type="text"),
                MappingField(template_id=template.id, excel_column_name="实际完成率", system_field_name="actual_percent", field_type="percent"),
            ]
        )
        db.commit()

        matches = match_templates(db, project.id, columns, sheet_name="进度明细")
        assert len(matches) == 1
        assert matches[0].is_exact_match is True
        assert matches[0].match_score == 1.0
        assert matches[0].match_reason is not None
        assert "sheet" in matches[0].match_reason

        # 列序列一样但 sheet 名不同 → 仍是精确匹配（hash 命中），只是 reason 不带 sheet 部分
        matches_no_sheet = match_templates(db, project.id, columns, sheet_name="其他 Sheet")
        assert matches_no_sheet[0].is_exact_match is True
        assert matches_no_sheet[0].match_reason is not None
        assert "sheet" not in (matches_no_sheet[0].match_reason or "")
    finally:
        db.close()


def test_match_templates_sheet_name_boost_without_exact_hash() -> None:
    """sheet 名命中 + 字段相似度足够 → 加 10% 分，但不算 exact_match。"""
    db = SessionLocal()
    try:
        project = Project(name="sheet 加分测试")
        db.add(project)
        db.flush()
        template = MappingTemplate(
            project_id=project.id,
            name="部分匹配模板",
            sheet_name="管线进度",
            header_hash=compute_header_hash(["旧列1", "旧列2", "旧列3"]),  # 与当前列不同
        )
        db.add(template)
        db.flush()
        db.add_all(
            [
                MappingField(template_id=template.id, excel_column_name="工作内容", system_field_name="task_name", field_type="text"),
                MappingField(template_id=template.id, excel_column_name="实际完成率", system_field_name="actual_percent", field_type="percent"),
            ]
        )
        db.commit()

        matches = match_templates(
            db,
            project.id,
            ["工作内容", "实际完成率", "新增的某一列"],
            sheet_name="管线进度",
        )
        assert len(matches) == 1
        assert matches[0].is_exact_match is False
        assert matches[0].match_reason is not None
        assert "sheet" in matches[0].match_reason
    finally:
        db.close()
