"""AI 兜底列名识别。

只有在 rule + history + fuzzy 都返回 None 之后才调用,避免每次解析都打 LLM。
- 模块内不直接调用 HTTP,而是接受一个 `chat_caller` 可调用对象,生产路径默认用
  app.services.ai_service.generate_ai_text 包装出来的版本,测试路径直接注入桩。
- 返回结果会写入 column_alias_history,后续遇到同名列就走历史命中而不走 AI。
- AI 调用失败/超时/格式异常一律静默兜底成 "保持原样"——不阻塞解析流程。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from app.models.project import Project
from app.schemas.ai import AiConfig
from app.services.ai_service import project_ai_config
from app.services.column_alias_service import record_alias

logger = logging.getLogger(__name__)


SYSTEM_FIELD_HINTS: list[tuple[str, str, str]] = [
    ("wbs_code", "WBS 编码/工作分解结构编码", "text"),
    ("task_code", "任务编码/清单编码/编号", "text"),
    ("task_name", "任务/工序/施工内容/分项工程名称", "text"),
    ("parent_task_name", "父级/上级任务名称", "text"),
    ("area", "施工区域", "text"),
    ("construction_unit", "施工单位/分包单位/责任单位", "text"),
    ("building", "楼栋/单体/楼号", "text"),
    ("floor", "楼层/层/所在楼层", "text"),
    ("discipline", "专业(电气/给排水/暖通/智能化...)", "text"),
    ("system_name", "系统名称(强电/消防/送排风...)", "text"),
    ("unit", "计量单位(米/台/套...)", "text"),
    ("total_quantity", "总工程量/设计量", "number"),
    ("planned_quantity", "计划完成量/应完成量", "number"),
    ("period_quantity", "本期完成量/本周完成量", "number"),
    ("cumulative_quantity", "累计完成量", "number"),
    ("actual_quantity", "实际完成量", "number"),
    ("remaining_quantity", "剩余量", "number"),
    ("planned_percent", "计划进度/计划完成率", "percent"),
    ("actual_percent", "实际进度/实际完成率/完成百分比", "percent"),
    ("reported_percent", "上报完成率", "percent"),
    ("planned_start_date", "计划开始日期", "date"),
    ("planned_finish_date", "计划完成/结束日期", "date"),
    ("actual_start_date", "实际开始日期", "date"),
    ("actual_finish_date", "实际完成/结束日期", "date"),
    ("weight", "权重/任务权重/占比", "number"),
    ("value_amount", "产值/金额", "currency"),
    ("status", "状态", "text"),
    ("remark", "备注/说明", "text"),
]

VALID_FIELD_TYPES = {"text", "number", "percent", "currency", "date", "unknown"}
VALID_SYSTEM_FIELDS = {hint[0] for hint in SYSTEM_FIELD_HINTS}

ChatCaller = Callable[[AiConfig, str, str], tuple[str, str | None]]


@dataclass
class AiColumnSuggestion:
    raw_header: str
    system_field: str
    field_type: str
    confidence: float
    reason: str | None = None


def _build_prompt(unresolved_headers: list[str]) -> tuple[str, str]:
    field_lines = "\n".join(
        f"- {field}: {description} (字段类型 {field_type})"
        for field, description, field_type in SYSTEM_FIELD_HINTS
    )
    header_lines = "\n".join(f"- {header}" for header in unresolved_headers)
    title = "工程进度 Excel 列名归一化"
    body = (
        "下面是若干来自工程进度 Excel 的「未识别」列名,请把每个列名映射到下表中"
        "最可能对应的系统字段,如果实在拿不准就返回 system_field 为 null。\n"
        "**只能从下面的字段名中挑选**,不要发明新字段:\n"
        f"{field_lines}\n\n"
        "需要映射的列名:\n"
        f"{header_lines}\n\n"
        "请只返回 JSON,格式严格按:\n"
        '{"mappings":[{"raw_header":"...","system_field":"...","field_type":"...",'
        '"confidence":0.0-1.0,"reason":"简短理由"}]}'
        "\nconfidence 表示你对这个映射的置信度。"
    )
    return title, body


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        # 去掉 ```json 或 ``` 包裹
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except (ValueError, TypeError):
        return None


def parse_ai_response(raw_text: str) -> list[AiColumnSuggestion]:
    payload = _extract_json(raw_text)
    if not isinstance(payload, dict):
        return []
    mappings = payload.get("mappings")
    if not isinstance(mappings, list):
        return []
    suggestions: list[AiColumnSuggestion] = []
    for entry in mappings:
        if not isinstance(entry, dict):
            continue
        raw_header = entry.get("raw_header")
        system_field = entry.get("system_field")
        if not raw_header or not system_field:
            continue
        if system_field not in VALID_SYSTEM_FIELDS:
            continue
        field_type = entry.get("field_type") or "unknown"
        if field_type not in VALID_FIELD_TYPES:
            field_type = "unknown"
        confidence_raw = entry.get("confidence")
        try:
            confidence = float(confidence_raw) if confidence_raw is not None else 0.5
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        reason = entry.get("reason") if isinstance(entry.get("reason"), str) else None
        suggestions.append(
            AiColumnSuggestion(
                raw_header=str(raw_header),
                system_field=system_field,
                field_type=field_type,
                confidence=confidence,
                reason=reason,
            )
        )
    return suggestions


def _default_chat_caller(config: AiConfig, title: str, body: str) -> tuple[str, str | None]:
    """生产路径:复用 ai_service.generate_ai_text 的 HTTP 逻辑,但绕过 mode 模板。"""
    from app.services.ai_service import generate_ai_text

    payload = {"title": title, "body": body}
    text, error_message, _ = generate_ai_text(config, "column_mapping", payload, prompt_template=body)
    return text, error_message


def suggest_columns_with_ai(
    unresolved_headers: list[str],
    *,
    config: AiConfig,
    chat_caller: ChatCaller | None = None,
    confidence_threshold: float = 0.6,
) -> list[AiColumnSuggestion]:
    if not unresolved_headers:
        return []
    if not config.enabled or not config.api_base_url or not config.api_key or not config.model:
        return []
    caller = chat_caller or _default_chat_caller
    title, body = _build_prompt(unresolved_headers)
    try:
        text, error_message = caller(config, title, body)
    except Exception:  # noqa: BLE001
        logger.exception("AI 列名兜底调用异常")
        return []
    if error_message or not text:
        return []
    suggestions = parse_ai_response(text)
    return [s for s in suggestions if s.confidence >= confidence_threshold]


def apply_ai_fallback_to_columns(
    db: Session,
    *,
    project_id: int | None,
    columns: list[dict],
    chat_caller: ChatCaller | None = None,
    confidence_threshold: float = 0.6,
    auto_accept_threshold: float = 0.85,
) -> list[dict]:
    """在 enrich_columns_with_aliases 之后调用——对仍未识别的列尝试 AI 兜底。

    AI 命中的列会:
      - 写回 columns[i]["recommended_field"] / field_type / alias_source="ai_fallback" / alias_confidence
      - 低于 auto_accept_threshold 但仍 >= confidence_threshold 的建议会被打上
        needs_review=True,前端应当突出展示要求用户人工确认——AI 大概率猜对了,但
        别让它默默写入历史导致下次"再也不会被复核"
      - 高于等于 auto_accept_threshold 的建议直接 needs_review=False
      - 写入 column_alias_history (project_id 维度),下次同名列直接走历史
    AI 配置未开启或调用失败,函数静默返回原 columns(不抛异常)。
    """
    if not columns:
        return columns
    unresolved_indices = [
        index
        for index, column in enumerate(columns)
        if not column.get("recommended_field")
    ]
    if not unresolved_indices:
        return columns

    config: AiConfig | None = None
    if project_id is not None:
        project = db.get(Project, project_id)
        if project is not None:
            config = project_ai_config(project)
    if config is None or not config.enabled:
        return columns

    unresolved_headers = [str(columns[i].get("name") or "") for i in unresolved_indices]
    suggestions = suggest_columns_with_ai(
        unresolved_headers,
        config=config,
        chat_caller=chat_caller,
        confidence_threshold=confidence_threshold,
    )
    if not suggestions:
        return columns

    suggestion_by_header = {s.raw_header: s for s in suggestions}
    for index in unresolved_indices:
        header = str(columns[index].get("name") or "")
        suggestion = suggestion_by_header.get(header)
        if suggestion is None:
            continue
        column = columns[index]
        column["recommended_field"] = suggestion.system_field
        if column.get("field_type") in (None, "unknown"):
            column["field_type"] = suggestion.field_type
        column["alias_source"] = "ai_fallback"
        column["alias_confidence"] = suggestion.confidence
        column["save_to_extra"] = False
        # 中等置信度的 AI 建议要让用户人工复核——别让 AI 默默把"还差点意思"的猜测
        # 写成既成事实,否则历史命中机制会让它永远不再被审视。
        column["needs_review"] = suggestion.confidence < auto_accept_threshold
        field_type = column.get("field_type") or "unknown"
        column["is_dimension"] = field_type == "text"
        column["is_metric"] = field_type in {"number", "percent", "currency"}
        # 只把"高置信度自动接受"的 AI 结果写入历史——needs_review 的中等结果先不入历史,
        # 等用户在 UI 上确认/修改后,confirm 路径会通过 record_aliases_bulk 落历史。
        if not column["needs_review"]:
            try:
                record_alias(
                    db,
                    project_id=project_id,
                    raw_header=header,
                    system_field=suggestion.system_field,
                    field_type=suggestion.field_type,
                )
            except Exception:  # noqa: BLE001
                logger.exception("AI 兜底结果写入 column_alias_history 失败,跳过")
    return columns
