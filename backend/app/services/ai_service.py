from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, request as urlrequest

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_call_log import AiCallLog
from app.models.ai_prompt_template import AiPromptTemplate
from app.models.project import Project
from app.models.rectification_item import RectificationItem
from app.schemas.ai import AiConfig, AiConfigRead
from app.services.analytics_service import (
    aggregate_progress,
    apply_time_based_progress,
    delayed_items as analytics_delayed_items,
    delay_reference_date,
    effective_baseline_plan,
    filter_items_by_baseline,
    get_published_batch,
    list_items,
    resolve_calculation_profile,
)
from app.services.progress_insight_service import generate_progress_insight

AI_MODES = {"dashboard_summary", "weekly_report_text", "delay_reason_analysis", "rectification_suggestions", "meeting_summary"}
AI_SECURITY_NOTICE = "AI 辅助生成内容仅供参考，请结合现场实际复核。请勿上传敏感数据或涉密工程资料到外部 AI 服务。"

BUILTIN_PROMPT_TEMPLATES = [
    {
        "name": "Dashboard 进度分析",
        "code": "dashboard_summary",
        "description": "用于项目进度看板的简明进度分析说明。",
        "prompt_template": "请基于结构化摘要，生成中文 Dashboard 进度分析说明。重点说明总体进度、主要滞后专业/楼层、风险点和建议动作，语言简洁，避免编造数据。",
    },
    {
        "name": "Word 周报分析说明",
        "code": "weekly_report_text",
        "description": "用于 Word 周报中的进度分析说明文字。",
        "prompt_template": "请基于结构化摘要，生成一段适合工程周报的中文进度分析说明。包含进度偏差、重点滞后项、整改闭环和下周建议。",
    },
    {
        "name": "滞后原因分析",
        "code": "delay_reason_analysis",
        "description": "用于分析滞后原因和协调重点。",
        "prompt_template": "请基于结构化摘要，生成中文滞后原因分析。区分可能的资源、材料、交叉作业、计划偏差和数据质量原因，并提醒现场复核。",
    },
    {
        "name": "整改建议",
        "code": "rectification_suggestions",
        "description": "用于单个整改项的建议生成。",
        "prompt_template": "请基于当前整改信息，生成中文整改建议。建议应可执行，包含责任、措施、时限和复查要点，不要修改任何业务数据。",
    },
    {
        "name": "会议汇报摘要",
        "code": "meeting_summary",
        "description": "用于会议汇报场景的摘要发言稿。",
        "prompt_template": "请基于结构化摘要，生成面向项目例会的中文汇报摘要。包含当前进度、主要风险、需协调事项和闭环要求。",
    },
]


def resolve_ai_config(raw_config: str | None) -> AiConfig:
    if not raw_config:
        return AiConfig()
    try:
        parsed = json.loads(raw_config)
    except json.JSONDecodeError:
        return AiConfig()
    if not isinstance(parsed, dict):
        return AiConfig()
    try:
        timeout_seconds = max(1, int(parsed.get("timeout_seconds", 20)))
    except (TypeError, ValueError):
        timeout_seconds = 20
    return AiConfig(
        enabled=bool(parsed.get("enabled", False)),
        api_base_url=_clean_text(parsed.get("api_base_url")),
        api_key=_clean_text(parsed.get("api_key")),
        model=_clean_text(parsed.get("model")),
        timeout_seconds=timeout_seconds,
    )


def resolve_ai_config_meta(raw_config: str | None) -> dict[str, Any]:
    if not raw_config:
        return {}
    try:
        parsed = json.loads(raw_config)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def serialize_ai_config(config: AiConfig) -> str:
    return json.dumps(config.model_dump(), ensure_ascii=False)


def serialize_ai_config_with_meta(config: AiConfig, meta: dict[str, Any] | None = None) -> str:
    data = config.model_dump()
    if meta:
        for key in ("last_test_result", "last_test_at"):
            if key in meta:
                data[key] = meta[key]
    return json.dumps(data, ensure_ascii=False, default=str)


def ai_config_read(config: AiConfig, last_test_result: str | None = None, last_test_at=None, last_call_at=None) -> AiConfigRead:
    return AiConfigRead(
        enabled=config.enabled,
        api_base_url=config.api_base_url,
        api_key_set=bool(config.api_key),
        model=config.model,
        timeout_seconds=config.timeout_seconds,
        last_test_result=last_test_result,
        last_test_at=last_test_at,
        last_call_at=last_call_at,
    )


def project_ai_config(project: Project) -> AiConfig:
    return resolve_ai_config(project.ai_config)


@dataclass
class AiInsightPayload:
    project_name: str
    data_date: str | None
    actual_percent: float | None
    planned_percent: float | None
    progress_deviation: float | None
    discipline_summary: str
    floor_summary: str
    building_floor_summary: str
    delayed_items: list[dict[str, Any]]
    rectification_summary: dict[str, Any]
    quality_summary: str


def build_ai_insight_payload(
    db: Session,
    project_id: int,
    batch_id: int | None = None,
    calculation_profile_id: int | None = None,
    baseline_plan_id: int | None = None,
    building: str | None = None,
) -> AiInsightPayload:
    batch = get_published_batch(db, project_id, batch_id)
    if batch is None:
        raise LookupError("Published import batch not found")
    profile = resolve_calculation_profile(db, project_id, calculation_profile_id or batch.calculation_profile_id)
    baseline = effective_baseline_plan(db, project_id, batch, baseline_plan_id)
    items = filter_items_by_baseline(apply_time_based_progress(list_items(db, project_id, batch.id), batch, profile), baseline)
    actual_percent, _, _ = aggregate_progress(items, profile, "actual_percent")
    planned_percent, _, _ = aggregate_progress(items, profile, "planned_percent")
    progress_deviation = round(actual_percent - planned_percent, 4) if actual_percent is not None and planned_percent is not None else None
    delayed_items: list[dict[str, Any]] = []
    delayed = analytics_delayed_items(items, delay_reference_date(batch))
    for item in delayed[:20]:
        delayed_items.append(
            {
                "discipline": item.discipline,
                "building": item.building,
                "floor": item.floor,
                "task_name": item.task_name,
                "system_name": item.system_name,
                "actual_percent": item.actual_percent,
                "planned_percent": item.planned_percent,
                "progress_deviation": item.progress_deviation,
            }
        )
    project = db.get(Project, project_id)
    insight = generate_progress_insight(db, project_id, batch.id, calculation_profile_id, baseline_plan_id, building)
    return AiInsightPayload(
        project_name=project.name if project else "",
        data_date=batch.data_date.isoformat() if batch.data_date else None,
        actual_percent=actual_percent,
        planned_percent=planned_percent,
        progress_deviation=progress_deviation,
        discipline_summary=insight.discipline_summary,
        floor_summary=insight.floor_summary,
        building_floor_summary=insight.building_floor_summary,
        delayed_items=delayed_items,
        rectification_summary=_rectification_summary(db, project_id, batch.id),
        quality_summary=insight.quality_summary,
    )


def rectification_ai_payload(item: RectificationItem) -> dict[str, Any]:
    return {
        "task_name": item.task_name,
        "issue_description": item.issue_description,
        "discipline": item.discipline,
        "building": item.building,
        "floor": item.floor,
        "system_name": item.system_name,
        "delay_level": item.delay_level,
        "actual_percent": item.actual_percent,
        "planned_percent": item.planned_percent,
        "progress_deviation": item.progress_deviation,
        "responsible_person": item.responsible_person,
        "responsible_unit": item.responsible_unit,
        "planned_finish_date": item.planned_finish_date.isoformat() if item.planned_finish_date else None,
        "status": item.status,
        "review_result": item.review_result,
        "remark": item.remark,
    }


def ensure_builtin_prompt_templates(db: Session) -> None:
    for template in BUILTIN_PROMPT_TEMPLATES:
        existing = db.scalar(
            select(AiPromptTemplate).where(
                AiPromptTemplate.code == template["code"],
                AiPromptTemplate.is_builtin.is_(True),
            )
        )
        if existing is None:
            db.add(AiPromptTemplate(project_id=None, is_builtin=True, is_active=True, **template))
    db.commit()


def prompt_title_for_mode(db: Session | None, mode: str, project_id: int | None = None) -> str:
    if db is not None:
        template = _active_prompt_template(db, mode, project_id)
        if template is not None:
            return template.prompt_template
    builtin = next((template for template in BUILTIN_PROMPT_TEMPLATES if template["code"] == mode), None)
    if builtin:
        return builtin["prompt_template"]
    return "请基于结构化摘要，生成中文工程进度分析建议。"


def build_mode_prompt(mode: str, payload: AiInsightPayload | dict[str, Any], prompt_template: str | None = None) -> tuple[str, str]:
    title = prompt_template or prompt_title_for_mode(None, mode)
    body = json.dumps(payload if isinstance(payload, dict) else payload.__dict__, ensure_ascii=False, indent=2)
    return title, body


def generate_ai_text(config: AiConfig, mode: str, payload: AiInsightPayload | dict[str, Any], prompt_template: str | None = None) -> tuple[str, str | None, dict[str, int | None]]:
    if not config.enabled or not config.api_base_url or not config.api_key or not config.model:
        return "", "AI 未启用或配置不完整", {}
    title, body = build_mode_prompt(mode, payload, prompt_template)
    endpoint = config.api_base_url.rstrip("/") + "/v1/chat/completions"
    request_body = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": f"你是工程进度分析助手，只能输出文字建议，不得修改任何业务数据。{AI_SECURITY_NOTICE}"},
            {"role": "user", "content": f"{title}\n\n{body}"},
        ],
        "temperature": 0.2,
    }
    req = urlrequest.Request(
        endpoint,
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        },
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=config.timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="ignore")
    except (TimeoutError, socket.timeout):
        return "", "AI 调用超时", {}
    except error.URLError as exc:
        reason = getattr(exc, "reason", None)
        return "", f"AI 调用失败：{reason or exc}", {}

    try:
        parsed = json.loads(raw)
        content = parsed["choices"][0]["message"]["content"]
        usage = parsed.get("usage") if isinstance(parsed, dict) else {}
    except Exception:
        return "", "AI 返回格式异常", {}

    text = str(content).strip()
    if not text:
        return "", "AI 返回空内容", {}
    return text, None, {
        "prompt_tokens": _optional_int(usage.get("prompt_tokens") if isinstance(usage, dict) else None),
        "completion_tokens": _optional_int(usage.get("completion_tokens") if isinstance(usage, dict) else None),
    }


def generate_ai_text_with_logging(
    db: Session,
    project_id: int | None,
    batch_id: int | None,
    config: AiConfig,
    mode: str,
    payload: AiInsightPayload | dict[str, Any],
    fallback_text: str,
) -> tuple[str, str | None, str]:
    started = time.perf_counter()
    prompt_template = prompt_title_for_mode(db, mode, project_id)
    text = ""
    error_message: str | None = None
    usage: dict[str, int | None] = {}
    source = "rule_fallback"
    try:
        text, error_message, usage = generate_ai_text(config, mode, payload, prompt_template)
        if text and not error_message:
            source = "ai"
            output_text = text
        else:
            output_text = fallback_text
    except Exception:
        error_message = "后端 AI 调用异常"
        output_text = fallback_text
    duration_ms = int((time.perf_counter() - started) * 1000)
    db.add(
        AiCallLog(
            project_id=project_id,
            batch_id=batch_id,
            mode=mode,
            model=config.model,
            source=source,
            success=source == "ai",
            error_message=error_message,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            input_summary_length=len(json.dumps(payload if isinstance(payload, dict) else payload.__dict__, ensure_ascii=False)),
            output_length=len(output_text or ""),
            duration_ms=duration_ms,
        )
    )
    db.flush()
    return output_text, error_message, source


def fallback_insight_text(
    db: Session,
    project_id: int,
    batch_id: int | None,
    calculation_profile_id: int | None,
    baseline_plan_id: int | None,
    building: str | None,
) -> str:
    insight = generate_progress_insight(db, project_id, batch_id, calculation_profile_id, baseline_plan_id, building)
    return "\n".join(
        [
            insight.overview_summary,
            insight.discipline_summary,
            insight.floor_summary,
            insight.building_floor_summary,
            insight.delay_summary,
            insight.quality_summary,
            *insight.focus_points,
            *insight.recommended_actions,
        ]
    )


def rectification_suggestion_fallback(item: RectificationItem) -> str:
    parts = [
        f"针对“{item.task_name or '当前整改项'}”，建议先核实现场实际完成情况与计划偏差，明确滞后原因、责任单位和责任人。",
        "请补充具体整改措施、计划完成时间和复查节点，整改过程中保留现场照片或验收记录。",
    ]
    if item.progress_deviation is not None and item.progress_deviation < 0:
        parts.append(f"当前偏差为 {item.progress_deviation:.1f} 个百分点，建议优先协调人员、材料和交叉作业影响。")
    if item.planned_finish_date:
        parts.append(f"计划完成时间为 {item.planned_finish_date.isoformat()}，请按期复查闭环。")
    return "\n".join(parts)


def _rectification_summary(db: Session, project_id: int, batch_id: int | None) -> dict[str, Any]:
    rows = list(
        db.query(RectificationItem)
        .filter(RectificationItem.project_id == project_id, RectificationItem.batch_id == batch_id)
        .all()
    )
    return {
        "total": len(rows),
        "open": sum(1 for row in rows if row.status == "open"),
        "in_progress": sum(1 for row in rows if row.status == "in_progress"),
        "completed": sum(1 for row in rows if row.status == "completed"),
        "closed": sum(1 for row in rows if row.status == "closed"),
        "ignored": sum(1 for row in rows if row.status == "ignored"),
    }


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _active_prompt_template(db: Session, mode: str, project_id: int | None) -> AiPromptTemplate | None:
    project_template = None
    if project_id is not None:
        project_template = db.scalar(
            select(AiPromptTemplate)
            .where(
                AiPromptTemplate.project_id == project_id,
                AiPromptTemplate.code == mode,
                AiPromptTemplate.is_active.is_(True),
            )
            .order_by(AiPromptTemplate.updated_at.desc(), AiPromptTemplate.id.desc())
        )
    if project_template is not None:
        return project_template
    return db.scalar(
        select(AiPromptTemplate)
        .where(
            AiPromptTemplate.project_id.is_(None),
            AiPromptTemplate.code == mode,
            AiPromptTemplate.is_builtin.is_(True),
            AiPromptTemplate.is_active.is_(True),
        )
        .order_by(AiPromptTemplate.id.asc())
    )


def _optional_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
