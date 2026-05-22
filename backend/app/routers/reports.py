from pathlib import Path

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.project import Project
from app.models.import_batch import ImportBatch
from app.models.rectification_item import RectificationItem
from app.models.report_export_record import ReportExportRecord
from app.schemas.report import ReportConfig, ReportExportRead, ReportPreviewResponse
from app.services.report_service import (
    DASHBOARD_EXCEL_TYPE,
    DELAY_RECTIFICATION_EXCEL_TYPE,
    REPORT_TYPES,
    WEEKLY_PDF_TYPE,
    WEEKLY_WORD_TYPE,
    create_dashboard_export,
    create_delay_rectification_export,
    create_report,
    create_weekly_pdf_report,
    create_weekly_word_report,
    resolve_report_config,
    serialize_report_config,
)
from app.services.analytics_service import baseline_context, effective_calculation_method, get_published_batch

router = APIRouter(prefix="/projects/{project_id}/reports", tags=["reports"])

REPORT_TYPE_ALIASES = {
    "delay_rectification": DELAY_RECTIFICATION_EXCEL_TYPE,
    "rectification_excel": DELAY_RECTIFICATION_EXCEL_TYPE,
    "delay_rectification_xlsx": DELAY_RECTIFICATION_EXCEL_TYPE,
}


def get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前项目不存在或已被清理。")
    return project


@router.get("/exports", response_model=list[ReportExportRead])
def list_report_exports(
    project_id: int,
    report_type: str | None = Query(default=None),
    project_name: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ReportExportRecord]:
    get_project_or_404(project_id, db)
    statement = select(ReportExportRecord).join(Project, Project.id == ReportExportRecord.project_id).where(ReportExportRecord.project_id == project_id)
    if report_type:
        normalized = REPORT_TYPE_ALIASES.get(report_type, report_type)
        statement = statement.where(ReportExportRecord.report_type == normalized)
    if project_name:
        statement = statement.where(Project.name.ilike(f"%{project_name}%"))
    if date_from:
        statement = statement.where(ReportExportRecord.exported_at >= datetime.combine(date_from, time.min))
    if date_to:
        statement = statement.where(ReportExportRecord.exported_at < datetime.combine(date_to + timedelta(days=1), time.min))
    if keyword:
        pattern = f"%{keyword}%"
        statement = statement.where(or_(ReportExportRecord.file_name.ilike(pattern), ReportExportRecord.file_path.ilike(pattern), Project.name.ilike(pattern)))
    return list(
        db.execute(
            statement.order_by(ReportExportRecord.exported_at.desc(), ReportExportRecord.id.desc())
        ).scalars()
    )


@router.get("/config", response_model=ReportConfig)
def get_report_config(project_id: int, db: Session = Depends(get_db)) -> ReportConfig:
    project = get_project_or_404(project_id, db)
    return resolve_report_config(project.report_config)


@router.put("/config", response_model=ReportConfig)
def update_report_config(project_id: int, payload: ReportConfig, db: Session = Depends(get_db)) -> ReportConfig:
    project = get_project_or_404(project_id, db)
    project.report_config = serialize_report_config(payload)
    db.commit()
    return payload


@router.get("/preview/{report_type}", response_model=ReportPreviewResponse)
def preview_report(
    project_id: int,
    report_type: str,
    batch_id: int | None = None,
    calculation_profile_id: int | None = Query(default=None),
    baseline_plan_id: int | None = Query(default=None),
    construction_unit: str | None = Query(default=None),
    building: str | None = Query(default=None),
    discipline: str | None = Query(default=None),
    floor: str | None = Query(default=None),
    system_name: str | None = Query(default=None),
    delay_level: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ReportPreviewResponse:
    project = get_project_or_404(project_id, db)
    normalized_type = REPORT_TYPE_ALIASES.get(report_type, report_type)
    if normalized_type == "dashboard_excel":
        batch = _preview_batch_or_none(db, project_id, batch_id)
        return ReportPreviewResponse(
            report_type=normalized_type,
            title="当前看板 Excel 预览",
            items=[
                {"label": "包含 Sheet 列表", "value": ["看板总览", "专业进度统计", "楼层进度统计", "楼栋楼层统计", "滞后项清单", "数据质量与校验问题汇总", "进度分析说明", "整改闭环摘要", "整改项明细", "专业进度对比", "楼层专业矩阵", "楼栋专业矩阵", "滞后分布统计"]},
                {"label": "当前筛选条件", "value": _filter_summary(building=building, discipline=discipline, floor=floor, delay_level=delay_level)},
                {"label": "当前批次", "value": _batch_label(batch)},
            ],
        )
    if normalized_type in {"weekly_word", WEEKLY_PDF_TYPE}:
        batch = _preview_batch_or_none(db, project_id, batch_id)
        config = resolve_report_config(project.report_config)
        baseline_meta = baseline_context(db, project_id, batch, baseline_plan_id) if batch else {}
        return ReportPreviewResponse(
            report_type=normalized_type,
            title="PDF 周报预览" if normalized_type == WEEKLY_PDF_TYPE else "Word 周报预览",
            items=[
                {"label": "项目名称", "value": project.name},
                {"label": "当前批次", "value": _batch_label(batch)},
                {"label": "数据日期", "value": batch.data_date.isoformat() if batch and batch.data_date else "-"},
                {"label": "计划基线", "value": str(baseline_meta.get("current_view_baseline_plan_name") or baseline_meta.get("batch_bound_baseline_plan_name") or "未配置计划基线")},
                {"label": "是否包含进阶图表分析", "value": config.include_advanced_chart_analysis},
                {"label": "是否包含整改闭环摘要", "value": config.show_rectification_summary},
                {"label": "主要滞后项最大条数", "value": config.weekly_delayed_item_limit},
                {"label": "矩阵摘要最大条数", "value": config.weekly_matrix_summary_limit},
            ],
        )
    if normalized_type == "rectification_tracking":
        count = _rectification_count(db, project_id, batch_id, status_filter, discipline, building, floor, keyword)
        return ReportPreviewResponse(
            report_type=normalized_type,
            title="整改跟踪表预览",
            items=[
                {"label": "当前筛选条件", "value": _filter_summary(status=status_filter, building=building, discipline=discipline, floor=floor, keyword=keyword)},
                {"label": "预计导出整改项数量", "value": count},
            ],
        )
    if normalized_type == "delay_rectification_excel":
        batch = _preview_batch_or_none(db, project_id, batch_id)
        return ReportPreviewResponse(
            report_type=normalized_type,
            title="整改清单预览",
            items=[
                {"label": "当前筛选条件", "value": _filter_summary(building=building, discipline=discipline, floor=floor, delay_level=delay_level)},
                {"label": "当前批次", "value": _batch_label(batch)},
            ],
        )
    if normalized_type == "maintenance_report":
        return ReportPreviewResponse(
            report_type=normalized_type,
            title="数据维护报告预览",
            items=[
                {"label": "项目名称", "value": project.name},
                {"label": "内容", "value": "本地数据体检、导出记录和维护状态摘要。"},
            ],
        )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "REPORT_TYPE_NOT_FOUND", "message": "报表类型不存在或未注册。"})


@router.get("/dashboard-export")
def export_dashboard(
    project_id: int,
    scope: str | None = Query(default=None),
    batch_id: int | None = None,
    data_date: date | None = Query(default=None),
    import_group_id: str | None = Query(default=None),
    batch_ids: str | None = Query(default=None),
    calculation_profile_id: int | None = Query(default=None),
    baseline_plan_id: int | None = Query(default=None),
    construction_unit: str | None = Query(default=None),
    building: str | None = Query(default=None),
    discipline: str | None = Query(default=None),
    floor: str | None = Query(default=None),
    system_name: str | None = Query(default=None),
    delay_level: str | None = Query(default=None),
    metric: str | None = Query(default=None),
    calculation_method: str | None = Query(default=None),
    export_format: str = Query(default="xlsx"),
    db: Session = Depends(get_db),
) -> FileResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PROJECT_NOT_FOUND", "message": "当前项目不存在或已被清理。"},
        )
    if export_format != "xlsx":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only xlsx export is supported")
    calculation_method = effective_calculation_method(project, calculation_method)
    try:
        record = create_dashboard_export(
            db,
            project,
            batch_id,
            calculation_profile_id,
            baseline_plan_id,
            building,
            discipline,
            floor,
            delay_level,
            metric,
            calculation_method,
            construction_unit=construction_unit,
            system_name=system_name,
            scope=scope,
            data_date=data_date,
            import_group_id=import_group_id,
            batch_ids=batch_ids,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NO_PUBLISHED_BATCH", "message": "当前暂无可导出数据。"}) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"code": "REPORT_GENERATION_FAILED", "message": "报表生成失败，请查看诊断日志。"}) from exc
    db.commit()
    db.refresh(record)
    file_path = Path(record.file_path or "")
    return FileResponse(
        path=file_path,
        filename=record.file_name or file_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/weekly-word")
def export_weekly_word(
    project_id: int,
    batch_id: int | None = None,
    calculation_profile_id: int | None = Query(default=None),
    baseline_plan_id: int | None = Query(default=None),
    building: str | None = Query(default=None),
    use_ai_text: bool = Query(default=False),
    calculation_method: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> FileResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PROJECT_NOT_FOUND", "message": "当前项目不存在或已被清理。"},
        )
    try:
        calculation_method = effective_calculation_method(project, calculation_method)
        record = create_weekly_word_report(db, project, batch_id, calculation_profile_id, baseline_plan_id, building, use_ai_text, calculation_method)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NO_PUBLISHED_BATCH", "message": "当前暂无可导出数据。"}) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"code": "REPORT_GENERATION_FAILED", "message": "报表生成失败，请查看诊断日志。"}) from exc
    db.commit()
    db.refresh(record)
    file_path = Path(record.file_path or "")
    return FileResponse(
        path=file_path,
        filename=record.file_name or file_path.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/weekly-pdf")
def export_weekly_pdf(
    project_id: int,
    batch_id: int | None = None,
    calculation_profile_id: int | None = Query(default=None),
    baseline_plan_id: int | None = Query(default=None),
    building: str | None = Query(default=None),
    use_ai: bool = Query(default=False),
    calculation_method: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> FileResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PROJECT_NOT_FOUND", "message": "当前项目不存在或已被清理。"},
        )
    try:
        calculation_method = effective_calculation_method(project, calculation_method)
        record = create_weekly_pdf_report(db, project, batch_id, calculation_profile_id, baseline_plan_id, building, use_ai, calculation_method)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NO_PUBLISHED_BATCH", "message": "当前暂无可导出数据。"}) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"code": "REPORT_GENERATION_FAILED", "message": "PDF 周报生成失败，请查看诊断日志。"}) from exc
    db.commit()
    db.refresh(record)
    file_path = Path(record.file_path or "")
    return FileResponse(
        path=file_path,
        filename=record.file_name or file_path.name,
        media_type="application/pdf",
    )


@router.get("/delay-rectification-export")
def export_delay_rectification(
    project_id: int,
    batch_id: int | None = None,
    calculation_profile_id: int | None = Query(default=None),
    baseline_plan_id: int | None = Query(default=None),
    building: str | None = Query(default=None),
    discipline: str | None = Query(default=None),
    floor: str | None = Query(default=None),
    delay_level: str | None = Query(default=None),
    calculation_method: str | None = Query(default=None),
    format: str = Query(default="xlsx"),
    db: Session = Depends(get_db),
) -> FileResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PROJECT_NOT_FOUND", "message": "当前项目不存在或已被清理。"},
        )
    if format != "xlsx":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only xlsx export is supported")
    delay_level = _normalize_delay_level(delay_level)
    if delay_level not in {None, "", "seriously_delayed", "delayed", "slightly_delayed"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported delay_level")
    try:
        calculation_method = effective_calculation_method(project, calculation_method)
        record = create_delay_rectification_export(
            db,
            project,
            batch_id,
            calculation_profile_id,
            baseline_plan_id,
            building,
            discipline,
            floor,
            delay_level,
            calculation_method,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NO_PUBLISHED_BATCH", "message": "当前暂无可导出数据。"}) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"code": "REPORT_GENERATION_FAILED", "message": "报表生成失败，请查看诊断日志。"}) from exc
    db.commit()
    db.refresh(record)
    file_path = Path(record.file_path or "")
    return FileResponse(
        path=file_path,
        filename=record.file_name or file_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _normalize_delay_level(value: str | None) -> str | None:
    labels = {
        "严重滞后": "seriously_delayed",
        "明显滞后": "delayed",
        "轻微滞后": "slightly_delayed",
        "seriously_delay": "seriously_delayed",
    }
    if value is None:
        return None
    cleaned = value.strip()
    return labels.get(cleaned, cleaned)


def _preview_batch_or_none(db: Session, project_id: int, batch_id: int | None) -> ImportBatch | None:
    return get_published_batch(db, project_id, batch_id)


def _batch_label(batch: ImportBatch | None) -> str:
    if batch is None:
        return "当前项目暂无已发布批次"
    parts = [f"#{batch.id}", batch.file_name]
    if batch.sheet_name:
        parts.append(batch.sheet_name)
    if batch.data_date:
        parts.append(batch.data_date.isoformat())
    return " / ".join(parts)


def _filter_summary(**filters: str | None) -> str:
    labels = {
        "status": "状态",
        "building": "楼栋",
        "discipline": "专业",
        "floor": "楼层",
        "delay_level": "滞后等级",
        "keyword": "关键词",
    }
    parts = [f"{labels.get(key, key)}={value}" for key, value in filters.items() if value]
    return "；".join(parts) if parts else "全部"


def _rectification_count(
    db: Session,
    project_id: int,
    batch_id: int | None,
    status_filter: str | None,
    discipline: str | None,
    building: str | None,
    floor: str | None,
    keyword: str | None,
) -> int:
    statement = select(func.count(RectificationItem.id)).where(RectificationItem.project_id == project_id)
    if batch_id is not None:
        statement = statement.where(RectificationItem.batch_id == batch_id)
    if status_filter:
        statuses = [value.strip() for value in status_filter.split(",") if value.strip()]
        if statuses:
            statement = statement.where(RectificationItem.status.in_(statuses))
    for field, value in {"discipline": discipline, "building": building, "floor": floor}.items():
        if value:
            statement = statement.where(getattr(RectificationItem, field) == value)
    if keyword:
        pattern = f"%{keyword}%"
        statement = statement.where(
            or_(
                RectificationItem.task_name.ilike(pattern),
                RectificationItem.system_name.ilike(pattern),
                RectificationItem.issue_description.ilike(pattern),
                RectificationItem.responsible_person.ilike(pattern),
                RectificationItem.responsible_unit.ilike(pattern),
                RectificationItem.remark.ilike(pattern),
                RectificationItem.review_result.ilike(pattern),
            )
        )
    return db.scalar(statement) or 0


@router.get("/{report_type}")
def export_report(
    project_id: int,
    report_type: str,
    batch_id: int | None = None,
    calculation_profile_id: int | None = Query(default=None),
    baseline_plan_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> FileResponse:
    project = get_project_or_404(project_id, db)
    report_type = REPORT_TYPE_ALIASES.get(report_type, report_type)
    if report_type not in REPORT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "REPORT_TYPE_NOT_FOUND", "message": "报表类型不存在或未注册。"},
        )
    try:
        if report_type == DASHBOARD_EXCEL_TYPE:
            record = create_dashboard_export(db, project, batch_id, calculation_profile_id, baseline_plan_id)
        elif report_type == WEEKLY_WORD_TYPE:
            record = create_weekly_word_report(db, project, batch_id, calculation_profile_id, baseline_plan_id)
        elif report_type == WEEKLY_PDF_TYPE:
            record = create_weekly_pdf_report(db, project, batch_id, calculation_profile_id, baseline_plan_id)
        elif report_type == DELAY_RECTIFICATION_EXCEL_TYPE:
            record = create_delay_rectification_export(db, project, batch_id, calculation_profile_id, baseline_plan_id)
        else:
            record = create_report(db, project_id, report_type, batch_id, calculation_profile_id, baseline_plan_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NO_PUBLISHED_BATCH", "message": "当前暂无可导出数据。"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"code": "REPORT_GENERATION_FAILED", "message": "报表生成失败，请查看诊断日志。"}) from exc
    db.commit()
    db.refresh(record)
    file_path = Path(record.file_path or "")
    extension = REPORT_TYPES[report_type]["extension"]
    media_type = (
        "application/pdf"
        if extension == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if extension == "docx"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return FileResponse(
        path=file_path,
        filename=record.file_name or file_path.name,
        media_type=media_type,
    )
