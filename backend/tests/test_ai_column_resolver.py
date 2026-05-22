import json

from app.database import SessionLocal
from app.models.column_alias_history import ColumnAliasHistory
from app.models.project import Project
from app.schemas.ai import AiConfig
from app.services.ai_column_resolver import (
    apply_ai_fallback_to_columns,
    parse_ai_response,
    suggest_columns_with_ai,
)


def _enabled_config() -> AiConfig:
    return AiConfig(
        enabled=True,
        api_base_url="https://example.invalid",
        api_key="test-key",
        model="test-model",
    )


def _project_with_ai(config: AiConfig) -> int:
    db = SessionLocal()
    try:
        project = Project(name="AI 兜底测试", ai_config=json.dumps(config.model_dump(), ensure_ascii=False))
        db.add(project)
        db.commit()
        return project.id
    finally:
        db.close()


def test_parse_ai_response_filters_invalid_fields_and_clamps_confidence() -> None:
    raw = """```json
{
  "mappings": [
    {"raw_header": "实际形象进度", "system_field": "actual_percent", "field_type": "percent", "confidence": 0.95, "reason": "通用别名"},
    {"raw_header": "随便列", "system_field": "不存在的字段", "field_type": "text", "confidence": 0.7},
    {"raw_header": "另一个", "system_field": "task_name", "field_type": "weird_type", "confidence": "1.8"}
  ]
}
```"""
    suggestions = parse_ai_response(raw)
    assert len(suggestions) == 2
    by_header = {s.raw_header: s for s in suggestions}
    assert by_header["实际形象进度"].system_field == "actual_percent"
    assert by_header["实际形象进度"].field_type == "percent"
    # field_type 不合法被改写成 unknown
    assert by_header["另一个"].field_type == "unknown"
    # confidence 被夹到 [0, 1]
    assert by_header["另一个"].confidence == 1.0


def test_suggest_columns_with_ai_skips_when_disabled() -> None:
    config = AiConfig(enabled=False)
    result = suggest_columns_with_ai(["x"], config=config, chat_caller=lambda c, t, b: ("ignored", None))
    assert result == []


def test_suggest_columns_with_ai_returns_high_confidence_only() -> None:
    fake_response = json.dumps(
        {
            "mappings": [
                {"raw_header": "实际形象进度", "system_field": "actual_percent", "field_type": "percent", "confidence": 0.95},
                {"raw_header": "其他", "system_field": "remark", "field_type": "text", "confidence": 0.3},
            ]
        },
        ensure_ascii=False,
    )

    def fake_caller(config, title, body):
        return fake_response, None

    result = suggest_columns_with_ai(
        ["实际形象进度", "其他"],
        config=_enabled_config(),
        chat_caller=fake_caller,
    )
    assert len(result) == 1
    assert result[0].raw_header == "实际形象进度"


def test_apply_ai_fallback_writes_history_and_skips_resolved_columns() -> None:
    project_id = _project_with_ai(_enabled_config())
    columns = [
        {"name": "WBS编码", "recommended_field": "wbs_code", "field_type": "text"},
        {"name": "实际形象进度", "recommended_field": None, "field_type": "unknown"},
        {"name": "完全陌生的列", "recommended_field": None, "field_type": "unknown"},
    ]

    def fake_caller(config, title, body):
        # 只对"实际形象进度"给出高置信度建议;陌生列给低置信度
        return (
            json.dumps(
                {
                    "mappings": [
                        {"raw_header": "实际形象进度", "system_field": "actual_percent", "field_type": "percent", "confidence": 0.9},
                        {"raw_header": "完全陌生的列", "system_field": "remark", "field_type": "text", "confidence": 0.2},
                    ]
                },
                ensure_ascii=False,
            ),
            None,
        )

    db = SessionLocal()
    try:
        result = apply_ai_fallback_to_columns(db, project_id=project_id, columns=columns, chat_caller=fake_caller)
        db.commit()
    finally:
        db.close()

    # 第 1 列已识别,保持原状
    assert result[0]["recommended_field"] == "wbs_code"
    assert result[0].get("alias_source") in (None, "rule")
    # 第 2 列被 AI 兜底
    assert result[1]["recommended_field"] == "actual_percent"
    assert result[1]["field_type"] == "percent"
    assert result[1]["alias_source"] == "ai_fallback"
    assert result[1]["alias_confidence"] == 0.9
    assert result[1]["save_to_extra"] is False
    # 第 3 列置信度太低,被丢弃
    assert result[2]["recommended_field"] is None

    # column_alias_history 应当落下一条 ai_fallback 记录
    db = SessionLocal()
    try:
        rows = db.query(ColumnAliasHistory).filter(ColumnAliasHistory.project_id == project_id).all()
        assert len(rows) == 1
        assert rows[0].system_field == "actual_percent"
        assert rows[0].field_type == "percent"
    finally:
        db.close()


def test_apply_ai_fallback_silent_when_ai_disabled() -> None:
    project_id = _project_with_ai(AiConfig(enabled=False))
    columns = [{"name": "陌生列", "recommended_field": None, "field_type": "unknown"}]
    calls: list[str] = []

    def fake_caller(config, title, body):
        calls.append(body)
        return "{}", None

    db = SessionLocal()
    try:
        result = apply_ai_fallback_to_columns(db, project_id=project_id, columns=columns, chat_caller=fake_caller)
    finally:
        db.close()

    assert result[0]["recommended_field"] is None
    assert calls == []  # AI 关闭时不应进行调用


def test_apply_ai_fallback_silent_when_caller_raises() -> None:
    project_id = _project_with_ai(_enabled_config())
    columns = [{"name": "陌生列", "recommended_field": None, "field_type": "unknown"}]

    def broken_caller(config, title, body):
        raise RuntimeError("AI 服务挂了")

    db = SessionLocal()
    try:
        # 不应抛异常,应静默返回原 columns
        result = apply_ai_fallback_to_columns(db, project_id=project_id, columns=columns, chat_caller=broken_caller)
    finally:
        db.close()

    assert result[0]["recommended_field"] is None


def test_apply_ai_fallback_marks_medium_confidence_as_needs_review() -> None:
    """中等置信度的 AI 建议要打 needs_review=True 而不是默默接受——同时不应写入历史。"""
    project_id = _project_with_ai(_enabled_config())
    columns = [
        {"name": "中等列", "recommended_field": None, "field_type": "unknown"},
        {"name": "高分列", "recommended_field": None, "field_type": "unknown"},
    ]

    def fake_caller(config, title, body):
        return (
            json.dumps(
                {
                    "mappings": [
                        # 0.7 落在 [0.6, 0.85) 中等区间 → needs_review=True
                        {"raw_header": "中等列", "system_field": "remark", "field_type": "text", "confidence": 0.7},
                        # 0.95 >= 0.85 → needs_review=False
                        {"raw_header": "高分列", "system_field": "actual_percent", "field_type": "percent", "confidence": 0.95},
                    ]
                },
                ensure_ascii=False,
            ),
            None,
        )

    db = SessionLocal()
    try:
        result = apply_ai_fallback_to_columns(db, project_id=project_id, columns=columns, chat_caller=fake_caller)
        db.commit()
    finally:
        db.close()

    assert result[0]["recommended_field"] == "remark"
    assert result[0]["needs_review"] is True
    assert result[0]["alias_source"] == "ai_fallback"

    assert result[1]["recommended_field"] == "actual_percent"
    assert result[1]["needs_review"] is False

    # 只有高置信度结果会落历史——中等的等用户在 UI 上确认后再落
    db = SessionLocal()
    try:
        rows = db.query(ColumnAliasHistory).filter(ColumnAliasHistory.project_id == project_id).all()
        recorded_headers = {row.raw_header for row in rows}
        assert "高分列" in recorded_headers
        assert "中等列" not in recorded_headers
    finally:
        db.close()
