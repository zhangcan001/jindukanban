from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ai_call_log import AiCallLog
from app.models.ai_prompt_template import AiPromptTemplate
from app.models.project import Project
from app.models.rectification_item import RectificationItem
from app.schemas.ai import (
    AiCallLogRead,
    AiConfig,
    AiConfigRead,
    AiConnectionTestRequest,
    AiConnectionTestResponse,
    AiInsightRequest,
    AiInsightResponse,
    AiPromptTemplateCreate,
    AiPromptTemplateRead,
    AiPromptTemplateUpdate,
)
from app.services.ai_service import (
    AI_MODES,
    ai_config_read,
    build_ai_insight_payload,
    ensure_builtin_prompt_templates,
    fallback_insight_text,
    generate_ai_text,
    generate_ai_text_with_logging,
    project_ai_config,
    rectification_ai_payload,
    rectification_suggestion_fallback,
    resolve_ai_config_meta,
    serialize_ai_config_with_meta,
)

router = APIRouter(prefix="/projects/{project_id}/ai", tags=["ai"])


def get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "当前项目不存在或已被清理。"})
    return project


@router.get("/config", response_model=AiConfigRead)
def get_ai_config(project_id: int, db: Session = Depends(get_db)) -> AiConfigRead:
    project = get_project_or_404(project_id, db)
    meta = resolve_ai_config_meta(project.ai_config)
    last_call = db.scalar(
        select(AiCallLog).where(AiCallLog.project_id == project_id).order_by(AiCallLog.created_at.desc(), AiCallLog.id.desc())
    )
    return ai_config_read(
        project_ai_config(project),
        last_test_result=meta.get("last_test_result"),
        last_test_at=_parse_datetime(meta.get("last_test_at")),
        last_call_at=last_call.created_at if last_call else None,
    )


@router.put("/config", response_model=AiConfigRead)
def update_ai_config(project_id: int, payload: AiConfig, db: Session = Depends(get_db)) -> AiConfigRead:
    project = get_project_or_404(project_id, db)
    existing = project_ai_config(project)
    meta = resolve_ai_config_meta(project.ai_config)
    if payload.api_key is None:
        payload.api_key = existing.api_key
    project.ai_config = serialize_ai_config_with_meta(payload, meta)
    db.commit()
    return get_ai_config(project_id, db)


@router.post("/test-connection", response_model=AiConnectionTestResponse)
def test_connection(project_id: int, payload: AiConnectionTestRequest, db: Session = Depends(get_db)) -> AiConnectionTestResponse:
    project = get_project_or_404(project_id, db)
    existing = project_ai_config(project)
    config = AiConfig(
        enabled=True,
        api_base_url=payload.api_base_url or existing.api_base_url,
        api_key=payload.api_key if payload.api_key is not None else existing.api_key,
        model=payload.model or existing.model,
        timeout_seconds=payload.timeout_seconds or existing.timeout_seconds,
    )
    _, error_message, _ = generate_ai_text(config, "dashboard_summary", _test_payload())
    success = not bool(error_message)
    tested_at = datetime.now()
    message = "AI 连接测试成功。" if success else f"连接失败：{error_message}"
    meta = resolve_ai_config_meta(project.ai_config)
    meta["last_test_result"] = message
    meta["last_test_at"] = tested_at.isoformat()
    project.ai_config = serialize_ai_config_with_meta(existing, meta)
    db.commit()
    return AiConnectionTestResponse(success=success, message=message, tested_at=tested_at)


@router.post("/insight", response_model=AiInsightResponse)
def ai_insight(project_id: int, payload: AiInsightRequest, db: Session = Depends(get_db)) -> AiInsightResponse:
    project = get_project_or_404(project_id, db)
    config = project_ai_config(project)
    if payload.mode not in AI_MODES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "UNSUPPORTED_AI_MODE", "message": "不支持的 AI 分析模式。"})

    fallback_text = fallback_insight_text(
        db,
        project_id,
        payload.batch_id,
        payload.calculation_profile_id,
        payload.baseline_plan_id,
        payload.building,
    )
    if not config.enabled or not config.api_base_url or not config.api_key or not config.model:
        _write_ai_log(db, project_id, payload.batch_id, payload.mode, config.model, "rule_fallback", False, "当前未启用 AI 辅助", 0, len(fallback_text))
        db.commit()
        return AiInsightResponse(enabled=False, generated_text=fallback_text, fallback_text=fallback_text, source="rule_fallback", error_message="当前未启用 AI 辅助")

    try:
        ai_payload = build_ai_insight_payload(
            db,
            project_id,
            payload.batch_id,
            payload.calculation_profile_id,
            payload.baseline_plan_id,
            payload.building,
        )
        generated_text, error_message, source = generate_ai_text_with_logging(
            db,
            project_id,
            payload.batch_id,
            config,
            payload.mode,
            ai_payload,
            fallback_text,
        )
        db.commit()
        return AiInsightResponse(enabled=True, generated_text=generated_text, fallback_text=fallback_text, source=source, error_message=error_message)
    except Exception:
        _write_ai_log(db, project_id, payload.batch_id, payload.mode, config.model, "rule_fallback", False, "AI 辅助分析失败，已使用规则化分析。", 0, len(fallback_text))
        db.commit()
        return AiInsightResponse(enabled=True, generated_text=fallback_text, fallback_text=fallback_text, source="rule_fallback", error_message="AI 辅助分析失败，已使用规则化分析。")


@router.post("/weekly-preview", response_model=AiInsightResponse)
def ai_weekly_preview(project_id: int, payload: AiInsightRequest, db: Session = Depends(get_db)) -> AiInsightResponse:
    payload.mode = "weekly_report_text"
    return ai_insight(project_id, payload, db)


@router.post("/rectifications/{item_id}/suggestion", response_model=AiInsightResponse)
def ai_rectification_suggestion(project_id: int, item_id: int, db: Session = Depends(get_db)) -> AiInsightResponse:
    project = get_project_or_404(project_id, db)
    item = db.get(RectificationItem, item_id)
    if item is None or item.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "RECTIFICATION_NOT_FOUND", "message": "整改项不存在。"})

    fallback_text = rectification_suggestion_fallback(item)
    config = project_ai_config(project)
    if not config.enabled or not config.api_base_url or not config.api_key or not config.model:
        _write_ai_log(db, project_id, item.batch_id, "rectification_suggestions", config.model, "rule_fallback", False, "当前未启用 AI 辅助", 0, len(fallback_text))
        db.commit()
        return AiInsightResponse(enabled=False, generated_text=fallback_text, fallback_text=fallback_text, source="rule_fallback", error_message="当前未启用 AI 辅助")

    try:
        generated_text, error_message, source = generate_ai_text_with_logging(
            db,
            project_id,
            item.batch_id,
            config,
            "rectification_suggestions",
            {"rectification": rectification_ai_payload(item)},
            fallback_text,
        )
        db.commit()
        return AiInsightResponse(enabled=True, generated_text=generated_text, fallback_text=fallback_text, source=source, error_message=error_message)
    except Exception:
        _write_ai_log(db, project_id, item.batch_id, "rectification_suggestions", config.model, "rule_fallback", False, "AI 辅助生成整改建议失败，已使用规则化建议。", 0, len(fallback_text))
        db.commit()
        return AiInsightResponse(enabled=True, generated_text=fallback_text, fallback_text=fallback_text, source="rule_fallback", error_message="AI 辅助生成整改建议失败，已使用规则化建议。")


@router.get("/templates", response_model=list[AiPromptTemplateRead])
def list_prompt_templates(project_id: int, db: Session = Depends(get_db)) -> list[AiPromptTemplate]:
    get_project_or_404(project_id, db)
    ensure_builtin_prompt_templates(db)
    statement = (
        select(AiPromptTemplate)
        .where((AiPromptTemplate.project_id.is_(None)) | (AiPromptTemplate.project_id == project_id))
        .order_by(AiPromptTemplate.is_builtin.desc(), AiPromptTemplate.code.asc(), AiPromptTemplate.id.asc())
    )
    return list(db.scalars(statement).all())


@router.post("/templates", response_model=AiPromptTemplateRead, status_code=status.HTTP_201_CREATED)
def create_prompt_template(project_id: int, payload: AiPromptTemplateCreate, db: Session = Depends(get_db)) -> AiPromptTemplate:
    get_project_or_404(project_id, db)
    template = AiPromptTemplate(
        project_id=project_id,
        name=payload.name,
        code=payload.code,
        description=payload.description,
        prompt_template=payload.prompt_template,
        is_builtin=False,
        is_active=payload.is_active,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.post("/templates/{template_id}/copy", response_model=AiPromptTemplateRead, status_code=status.HTTP_201_CREATED)
def copy_prompt_template(project_id: int, template_id: int, db: Session = Depends(get_db)) -> AiPromptTemplate:
    get_project_or_404(project_id, db)
    source = db.get(AiPromptTemplate, template_id)
    if source is None or (source.project_id not in {None, project_id}):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt template not found")
    copied = AiPromptTemplate(
        project_id=project_id,
        name=f"{source.name} 副本",
        code=source.code,
        description=source.description,
        prompt_template=source.prompt_template,
        is_builtin=False,
        is_active=True,
    )
    db.add(copied)
    db.commit()
    db.refresh(copied)
    return copied


@router.patch("/templates/{template_id}", response_model=AiPromptTemplateRead)
def update_prompt_template(project_id: int, template_id: int, payload: AiPromptTemplateUpdate, db: Session = Depends(get_db)) -> AiPromptTemplate:
    get_project_or_404(project_id, db)
    template = db.get(AiPromptTemplate, template_id)
    if template is None or template.project_id != project_id or template.is_builtin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="内置模板不可修改，请先复制后再编辑。")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    db.commit()
    db.refresh(template)
    return template


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prompt_template(project_id: int, template_id: int, db: Session = Depends(get_db)) -> None:
    get_project_or_404(project_id, db)
    template = db.get(AiPromptTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt template not found")
    if template.is_builtin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="内置模板不可删除。")
    if template.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt template not found")
    db.delete(template)
    db.commit()


@router.get("/logs", response_model=list[AiCallLogRead])
def list_ai_logs(project_id: int, limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)) -> list[AiCallLog]:
    get_project_or_404(project_id, db)
    return list(
        db.scalars(
            select(AiCallLog)
            .where(AiCallLog.project_id == project_id)
            .order_by(AiCallLog.created_at.desc(), AiCallLog.id.desc())
            .limit(limit)
        ).all()
    )


def _write_ai_log(
    db: Session,
    project_id: int | None,
    batch_id: int | None,
    mode: str,
    model: str | None,
    source: str,
    success: bool,
    error_message: str | None,
    input_length: int,
    output_length: int,
) -> None:
    db.add(
        AiCallLog(
            project_id=project_id,
            batch_id=batch_id,
            mode=mode,
            model=model,
            source=source,
            success=success,
            error_message=error_message,
            input_summary_length=input_length,
            output_length=output_length,
            duration_ms=0,
        )
    )


def _parse_datetime(value: object):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _test_payload() -> dict[str, object]:
    return {
        "project_name": "测试项目",
        "data_date": None,
        "actual_percent": None,
        "planned_percent": None,
        "progress_deviation": None,
        "discipline_summary": "",
        "floor_summary": "",
        "building_floor_summary": "",
        "delayed_items": [],
        "rectification_summary": {},
        "quality_summary": "",
    }
