from datetime import datetime

from app.database import SessionLocal
from app.models.column_alias_history import ColumnAliasHistory
from app.models.project import Project
from app.services.column_alias_service import (
    enrich_columns_with_aliases,
    lookup_alias,
    record_alias,
    record_aliases_bulk,
)


def _make_project(db, name: str = "测试项目") -> Project:
    project = Project(name=name, project_type="general")
    db.add(project)
    db.flush()
    return project


def test_record_alias_creates_then_increments() -> None:
    with SessionLocal() as db:
        project = _make_project(db)
        record_alias(db, project_id=project.id, raw_header="完工进度", system_field="actual_percent", field_type="percent")
        record_alias(db, project_id=project.id, raw_header="完工进度", system_field="actual_percent", field_type="percent")
        db.commit()

        rows = list(db.query(ColumnAliasHistory))
        assert len(rows) == 1
        assert rows[0].hit_count == 2
        assert rows[0].system_field == "actual_percent"
        assert rows[0].last_used_at is not None


def test_record_alias_skips_empty_or_missing_field() -> None:
    with SessionLocal() as db:
        project = _make_project(db)
        record_alias(db, project_id=project.id, raw_header="", system_field="actual_percent")
        record_alias(db, project_id=project.id, raw_header="完工率", system_field="")
        db.commit()

        assert db.query(ColumnAliasHistory).count() == 0


def test_lookup_alias_exact_match_prefers_higher_hit_count() -> None:
    with SessionLocal() as db:
        project = _make_project(db)
        # 两条 system_field 不同 → 唯一约束允许并存，按 hit_count 取胜
        record_alias(db, project_id=project.id, raw_header="完工率", system_field="actual_percent")
        record_alias(db, project_id=project.id, raw_header="完工率", system_field="reported_percent")
        record_alias(db, project_id=project.id, raw_header="完工率", system_field="actual_percent")
        db.commit()

        match = lookup_alias(db, project_id=project.id, raw_header="完工率")
        assert match is not None
        assert match.source == "history-exact"
        assert match.system_field == "actual_percent"
        assert match.confidence == 1.0


def test_lookup_alias_strips_punctuation_for_exact_match() -> None:
    """带百分号/括号装饰的列名应等同于无装饰列名。"""

    with SessionLocal() as db:
        project = _make_project(db)
        record_alias(db, project_id=project.id, raw_header="本期实际完工率", system_field="actual_percent")
        db.commit()

        match = lookup_alias(db, project_id=project.id, raw_header="本期实际完工率(%)")
        assert match is not None
        assert match.source == "history-exact"  # 标点剥离后等价于精确命中
        assert match.system_field == "actual_percent"


def test_lookup_alias_fuzzy_match_above_threshold() -> None:
    """同一字段加细化后缀（常见于监理表）应命中模糊匹配。"""

    with SessionLocal() as db:
        project = _make_project(db)
        record_alias(db, project_id=project.id, raw_header="施工内容", system_field="task_name")
        db.commit()

        # 在已知列名后追加描述词，是监理 Excel 最常见的变体
        match = lookup_alias(db, project_id=project.id, raw_header="施工内容描述")
        assert match is not None
        assert match.source == "history-fuzzy"
        assert match.system_field == "task_name"
        assert 0.75 <= match.confidence < 1.0


def test_lookup_alias_fuzzy_below_threshold_returns_none() -> None:
    with SessionLocal() as db:
        project = _make_project(db)
        record_alias(db, project_id=project.id, raw_header="完工进度", system_field="actual_percent")
        db.commit()

        match = lookup_alias(db, project_id=project.id, raw_header="施工单位")
        assert match is None


def test_lookup_alias_falls_back_to_global_scope() -> None:
    with SessionLocal() as db:
        project_a = _make_project(db, "项目甲")
        project_b = _make_project(db, "项目乙")
        # 全局别名（project_id=None）
        record_alias(db, project_id=None, raw_header="进度比例", system_field="actual_percent")
        db.commit()

        match = lookup_alias(db, project_id=project_b.id, raw_header="进度比例")
        assert match is not None
        assert match.system_field == "actual_percent"


def test_record_aliases_bulk_skips_none_system_field() -> None:
    with SessionLocal() as db:
        project = _make_project(db)
        record_aliases_bulk(
            db,
            project_id=project.id,
            mappings=[
                ("施工内容", "task_name", "text"),
                ("备注栏", None, None),  # 用户未映射
                ("完工率", "actual_percent", "percent"),
            ],
        )
        db.commit()

        assert db.query(ColumnAliasHistory).count() == 2


def test_enrich_columns_fills_unrecognized_columns() -> None:
    with SessionLocal() as db:
        project = _make_project(db)
        record_alias(db, project_id=project.id, raw_header="完工进度%", system_field="actual_percent", field_type="percent")
        db.commit()

        columns = [
            {"name": "施工内容", "field_type": "text", "recommended_field": "task_name", "is_dimension": True, "is_metric": False, "save_to_extra": False},
            {"name": "完工进度%", "field_type": "unknown", "recommended_field": None, "is_dimension": False, "is_metric": False, "save_to_extra": True},
            {"name": "完全不认识的列", "field_type": "unknown", "recommended_field": None, "is_dimension": False, "is_metric": False, "save_to_extra": True},
        ]
        enriched = enrich_columns_with_aliases(db, project_id=project.id, columns=columns)

        assert enriched[0]["alias_source"] == "rule"
        assert enriched[0]["alias_confidence"] == 1.0
        assert enriched[1]["recommended_field"] == "actual_percent"
        assert enriched[1]["alias_source"] == "history-exact"
        assert enriched[1]["save_to_extra"] is False
        assert enriched[1]["is_metric"] is True
        assert enriched[2]["recommended_field"] is None
        assert enriched[2]["alias_source"] is None
