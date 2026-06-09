from __future__ import annotations

from datetime import date, datetime, time, timedelta
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings
from app.models.import_batch import ImportBatch
from app.models.baseline_plan import BaselinePlan
from app.models.progress_item import ProgressItem
from app.models.project import Project
from app.models.rectification_action_log import RectificationActionLog
from app.models.rectification_item import RectificationItem
from app.models.report_export_record import ReportExportRecord
from app.models.warning_record import WarningRecord
from app.schemas.rectification import (
    RectificationActionLogRead,
    RectificationBatchUpdate,
    RectificationBatchUpdateResponse,
    RectificationCreate,
    RectificationCreateResponse,
    RectificationFilterOptions,
    RectificationFromDelayedItem,
    RectificationFromWarningRecord,
    RectificationListResponse,
    RectificationRead,
    RectificationStatusUpdate,
    RectificationSummary,
    RectificationUpdate,
)
from app.services.analytics_service import (
    apply_time_based_progress,
    build_delay_message,
    delay_level_for_deviation,
    display_text,
    effective_calculation_method,
    get_published_batch,
    is_delay_eligible,
    item_units,
    list_items,
    resolve_calculation_profile,
    statistics_context,
)
from app.services.warning_service import is_data_quality_warning_record

router = APIRouter(tags=["rectifications"])

CLOSED_STATUSES = {"closed", "ignored", "completed"}
FINAL_STATUSES = {"closed", "ignored"}
STATUS_LABELS = {
    "open": "未开始",
    "in_progress": "整改中",
    "completed": "已完成",
    "closed": "已关闭",
    "ignored": "已忽略",
}
ACTION_LABELS = {
    "create": "创建",
    "update": "编辑",
    "status_change": "状态变更",
    "close": "关闭",
    "ignore": "忽略",
    "export": "导出",
    "comment": "备注",
}
DELAY_LABELS = {
    "slightly_delayed": "轻微滞后",
    "delayed": "明显滞后",
    "seriously_delayed": "严重滞后",
    "seriously_delay": "严重滞后",
    "critical": "严重滞后",
    "warning": "明显滞后",
    "info": "轻微滞后",
}


def get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前项目不存在或已被清理。")
    return project


def ensure_project_not_archived(project: Project) -> None:
    if project.is_archived:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="项目已归档，不能新建整改项。")


@router.get("/projects/{project_id}/rectifications", response_model=RectificationListResponse)
def list_rectifications(
    project_id: int,
    scope: str | None = None,
    batch_id: int | None = None,
    data_date: date | None = None,
    import_group_id: str | None = None,
    batch_ids: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    delay_level: str | None = None,
    discipline: str | None = None,
    building: str | None = None,
    floor: str | None = None,
    responsible_person: str | None = None,
    responsible_unit: str | None = None,
    overdue: bool | None = None,
    source_type: str | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    sort_by: str | None = None,
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
) -> RectificationListResponse:
    get_project_or_404(project_id, db)
    scoped_batch_ids = _resolve_scope_batch_ids(db, project_id, scope, batch_id, data_date, import_group_id, batch_ids)
    statement = _filtered_statement(
        project_id,
        batch_id=batch_id,
        batch_ids=scoped_batch_ids,
        status_filter=status_filter,
        delay_level=delay_level,
        discipline=discipline,
        building=building,
        floor=floor,
        responsible_person=responsible_person,
        responsible_unit=responsible_unit,
        overdue=overdue,
        source_type=source_type,
        keyword=keyword,
    )
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    statement = _apply_sort(statement, sort_by, sort_order)
    rows = db.execute(statement.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return RectificationListResponse(items=[_read_item(row, db) for row in rows], total=total, page=page, page_size=page_size)


@router.get("/projects/{project_id}/rectifications/summary", response_model=RectificationSummary)
def rectification_summary(
    project_id: int,
    scope: str | None = None,
    batch_id: int | None = None,
    data_date: date | None = None,
    import_group_id: str | None = None,
    batch_ids: str | None = None,
    db: Session = Depends(get_db),
) -> RectificationSummary:
    get_project_or_404(project_id, db)
    scoped_batch_ids = _resolve_scope_batch_ids(db, project_id, scope, batch_id, data_date, import_group_id, batch_ids)
    rows = list(db.execute(_filtered_statement(project_id, batch_id=batch_id, batch_ids=scoped_batch_ids)).scalars())
    week_start = _week_start(datetime.now())
    return RectificationSummary(
        total=len(rows),
        open=sum(1 for row in rows if row.status == "open"),
        in_progress=sum(1 for row in rows if row.status == "in_progress"),
        completed=sum(1 for row in rows if row.status == "completed"),
        closed=sum(1 for row in rows if row.status == "closed"),
        ignored=sum(1 for row in rows if row.status == "ignored"),
        overdue=sum(1 for row in rows if _is_overdue(row)),
        serious=sum(1 for row in rows if row.delay_level in {"seriously_delayed", "seriously_delay", "critical"}),
        new_this_week=sum(1 for row in rows if row.created_at and row.created_at >= week_start),
        closed_this_week=sum(1 for row in rows if row.closed_at and row.closed_at >= week_start),
    )


@router.get("/projects/{project_id}/rectifications/filter-options", response_model=RectificationFilterOptions)
def list_rectification_filter_options(
    project_id: int,
    scope: str | None = None,
    batch_id: int | None = None,
    data_date: date | None = None,
    import_group_id: str | None = None,
    batch_ids: str | None = None,
    db: Session = Depends(get_db),
) -> RectificationFilterOptions:
    """返回当前 scope 下的整改下拉选项。

    存在的理由:前端 loadData() 之前会额外发一个 page_size=200 的请求只为 distinct
    出选项,数据 >200 时下拉项还会不全(隐藏 bug)。这里改成一次 DISTINCT。
    """
    get_project_or_404(project_id, db)
    scoped_batch_ids = _resolve_scope_batch_ids(db, project_id, scope, batch_id, data_date, import_group_id, batch_ids)
    statement = select(
        RectificationItem.discipline,
        RectificationItem.building,
        RectificationItem.floor,
        RectificationItem.responsible_person,
        RectificationItem.responsible_unit,
        RectificationItem.delay_level,
        RectificationItem.status,
        RectificationItem.source_type,
    ).where(RectificationItem.project_id == project_id)
    if scoped_batch_ids is not None:
        statement = statement.where(RectificationItem.batch_id.in_(scoped_batch_ids))
    elif batch_id is not None:
        statement = statement.where(RectificationItem.batch_id == batch_id)
    statement = statement.distinct()

    disciplines: set[str] = set()
    buildings: set[str] = set()
    floors: set[str] = set()
    responsible_persons: set[str] = set()
    responsible_units: set[str] = set()
    delay_levels: set[str] = set()
    statuses: set[str] = set()
    source_types: set[str] = set()
    floors_by_building: dict[str, set[str]] = {}

    for disc, bld, flr, person, unit, delay, st, src in db.execute(statement):
        if disc:
            disciplines.add(disc)
        if bld:
            buildings.add(bld)
        if flr:
            floors.add(flr)
        if person:
            responsible_persons.add(person)
        if unit:
            responsible_units.add(unit)
        if delay:
            delay_levels.add(delay)
        if st:
            statuses.add(st)
        if src:
            source_types.add(src)
        if bld and flr:
            floors_by_building.setdefault(bld, set()).add(flr)

    return RectificationFilterOptions(
        disciplines=sorted(disciplines),
        buildings=sorted(buildings),
        floors=sorted(floors),
        responsible_persons=sorted(responsible_persons),
        responsible_units=sorted(responsible_units),
        delay_levels=sorted(delay_levels),
        statuses=sorted(statuses),
        source_types=sorted(source_types),
        floors_by_building={k: sorted(v) for k, v in floors_by_building.items()},
    )


@router.post("/projects/{project_id}/rectifications", response_model=RectificationRead, status_code=status.HTTP_201_CREATED)
def create_rectification(project_id: int, payload: RectificationCreate, db: Session = Depends(get_db)) -> RectificationRead:
    project = get_project_or_404(project_id, db)
    ensure_project_not_archived(project)
    item = RectificationItem(project_id=project_id, **payload.model_dump())
    db.add(item)
    db.flush()
    _add_log(db, item, "create", None, item.status, "手动创建整改项")
    db.commit()
    db.refresh(item)
    return _read_item(item, db)


@router.post("/projects/{project_id}/rectifications/from-progress-items", response_model=RectificationCreateResponse)
def create_from_progress_item(project_id: int, payload: RectificationFromDelayedItem, db: Session = Depends(get_db)) -> RectificationCreateResponse:
    project = get_project_or_404(project_id, db)
    ensure_project_not_archived(project)
    progress_item = db.get(ProgressItem, payload.progress_item_id)
    if progress_item is None or progress_item.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Progress item not found")
    batch = db.get(ImportBatch, payload.batch_id)
    reference_date = (batch.data_date if batch else None) or date.today()
    if batch is not None:
        apply_time_based_progress([progress_item], batch)
    if not is_delay_eligible(progress_item, reference_date) or progress_item.progress_deviation is None or progress_item.progress_deviation >= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前任务尚未到计划开始时间或不属于滞后项，不能从滞后项生成整改项。")
    existing = db.scalar(
        select(RectificationItem).where(
            RectificationItem.project_id == project_id,
            RectificationItem.progress_item_id == progress_item.id,
            RectificationItem.source_type == "progress_item",
        )
    )
    if existing is not None:
        return RectificationCreateResponse(item=_read_item(existing, db), created=False, message="该滞后项已生成整改项。")
    delay_level, _ = delay_level_for_deviation(progress_item.progress_deviation)
    item = RectificationItem(
        project_id=project_id,
        batch_id=payload.batch_id,
        progress_item_id=progress_item.id,
        source_type="progress_item",
        source_id=progress_item.id,
        discipline=progress_item.discipline,
        building=progress_item.building,
        floor=progress_item.floor,
        system_name=progress_item.system_name,
        task_name=progress_item.task_name,
        issue_description=build_delay_message(progress_item),
        delay_level=delay_level,
        actual_percent=progress_item.actual_percent,
        planned_percent=progress_item.planned_percent,
        progress_deviation=progress_item.progress_deviation,
        status="open",
    )
    db.add(item)
    db.flush()
    _add_log(db, item, "create", None, item.status, "从滞后项生成整改项")
    db.commit()
    db.refresh(item)
    return RectificationCreateResponse(item=_read_item(item, db), created=True, message="整改项已生成。")


@router.post("/projects/{project_id}/rectifications/from-warnings", response_model=RectificationCreateResponse)
def create_from_warning(project_id: int, payload: RectificationFromWarningRecord, db: Session = Depends(get_db)) -> RectificationCreateResponse:
    project = get_project_or_404(project_id, db)
    ensure_project_not_archived(project)
    warning = db.get(WarningRecord, payload.warning_record_id)
    if warning is None or warning.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warning record not found")
    if is_data_quality_warning_record(warning):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="数据质量评分低属于批次质量提示，不能从该提示生成整改项。")
    progress_item = _progress_item_for_warning(db, warning)
    if progress_item is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该预警记录未关联具体施工项，不能生成整改项。")
    existing = db.scalar(
        select(RectificationItem).where(
            RectificationItem.project_id == project_id,
            RectificationItem.warning_record_id == warning.id,
            RectificationItem.source_type == "warning",
        )
    )
    if existing is not None:
        return RectificationCreateResponse(item=_read_item(existing, db), created=False, message="该预警记录已生成整改项。")
    level = _warning_delay_level(warning.level)
    item = RectificationItem(
        project_id=project_id,
        batch_id=warning.batch_id,
        progress_item_id=progress_item.id if progress_item else None,
        warning_record_id=warning.id,
        source_type="warning",
        source_id=warning.id,
        discipline=progress_item.discipline if progress_item else None,
        building=progress_item.building if progress_item else None,
        floor=progress_item.floor if progress_item else None,
        system_name=progress_item.system_name if progress_item else None,
        task_name=progress_item.task_name if progress_item else warning.title,
        issue_description=warning.message or warning.title,
        delay_level=level,
        actual_percent=progress_item.actual_percent if progress_item else None,
        planned_percent=progress_item.planned_percent if progress_item else None,
        progress_deviation=progress_item.progress_deviation if progress_item else None,
        status="open",
    )
    db.add(item)
    db.flush()
    _add_log(db, item, "create", None, item.status, "从预警记录生成整改项")
    db.commit()
    db.refresh(item)
    return RectificationCreateResponse(item=_read_item(item, db), created=True, message="整改项已生成。")


@router.post("/projects/{project_id}/rectifications/batch-update", response_model=RectificationBatchUpdateResponse)
def batch_update(project_id: int, payload: RectificationBatchUpdate, db: Session = Depends(get_db)) -> RectificationBatchUpdateResponse:
    get_project_or_404(project_id, db)
    ids = list(dict.fromkeys(payload.ids))
    if not ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids required")
    items = list(db.execute(select(RectificationItem).where(RectificationItem.project_id == project_id, RectificationItem.id.in_(ids))).scalars())
    found = {item.id for item in items}
    skipped_ids = [item_id for item_id in ids if item_id not in found]
    updated_count = 0
    for item in items:
        if item.status in FINAL_STATUSES and payload.status in FINAL_STATUSES | {"in_progress", "completed"}:
            skipped_ids.append(item.id)
            continue
        before = item.status
        changed: list[str] = []
        for field in ("responsible_person", "responsible_unit", "planned_finish_date", "remark"):
            value = getattr(payload, field)
            if value is not None and getattr(item, field) != value:
                setattr(item, field, value)
                changed.append(_field_label(field))
        if payload.status is not None and item.status != payload.status:
            item.status = payload.status
            changed.append("状态")
        if changed:
            _apply_closed_at(item, before)
            action = "close" if item.status == "closed" else "ignore" if item.status == "ignored" else "status_change" if before != item.status else "update"
            _add_log(db, item, action, before, item.status, f"批量更新：{'、'.join(changed)}")
            updated_count += 1
    db.commit()
    return RectificationBatchUpdateResponse(updated_count=updated_count, skipped_count=len(skipped_ids), skipped_ids=skipped_ids)


@router.get("/projects/{project_id}/rectifications/export")
def export_rectifications(
    project_id: int,
    scope: str | None = None,
    batch_id: int | None = None,
    data_date: date | None = None,
    import_group_id: str | None = None,
    batch_ids: str | None = None,
    baseline_plan_id: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    delay_level: str | None = None,
    discipline: str | None = None,
    building: str | None = None,
    floor: str | None = None,
    responsible_person: str | None = None,
    responsible_unit: str | None = None,
    overdue: bool | None = None,
    source_type: str | None = None,
    keyword: str | None = None,
    calculation_method: str | None = None,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    from openpyxl import Workbook

    project = get_project_or_404(project_id, db)
    method_context = _calculation_method_context(db, project, batch_id, calculation_method)
    scoped_batch_ids = _resolve_scope_batch_ids(db, project_id, scope, batch_id, data_date, import_group_id, batch_ids)
    items = list(
        db.execute(
            _apply_sort(
                _filtered_statement(
                    project_id,
                    batch_id=batch_id,
                    batch_ids=scoped_batch_ids,
                    status_filter=status_filter,
                    delay_level=delay_level,
                    discipline=discipline,
                    building=building,
                    floor=floor,
                    responsible_person=responsible_person,
                    responsible_unit=responsible_unit,
                    overdue=overdue,
                    source_type=source_type,
                    keyword=keyword,
                ),
                None,
                "desc",
            )
        ).scalars()
    )
    if not items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NO_RECTIFICATIONS_FOR_FILTER", "message": "当前筛选条件下暂无整改项。"},
        )
    _add_export_logs(db, items, "导出整改跟踪表")
    db.commit()
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "整改跟踪表"
    _fill_export_sheet(
        sheet,
        project,
        batch_id,
        items,
        {
            "status": status_filter,
            "discipline": discipline,
            "building": building,
            "floor": floor,
            "responsible_person": responsible_person,
            "overdue": overdue,
            "baseline_plan_id": baseline_plan_id,
        },
        db,
        method_context,
    )
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    data_date = None
    if batch_id:
        batch = db.get(ImportBatch, batch_id)
        data_date = batch.data_date if batch else None
    display_date = data_date or date.today()
    safe_project_name = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in project.name).strip("_") or f"project_{project.id}"
    file_name = f"{safe_project_name}_整改跟踪表_{display_date.isoformat()}.xlsx"
    export_dir = Path(get_settings().export_dir) / str(project_id)
    export_dir.mkdir(parents=True, exist_ok=True)
    file_path = export_dir / f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}_{file_name}"
    workbook.save(file_path)
    db.add(
        ReportExportRecord(
            project_id=project_id,
            batch_id=batch_id,
            report_type="rectification_tracking",
            file_name=file_name,
            file_path=str(file_path),
            data_date=data_date,
            exported_by="system",
        )
    )
    db.commit()
    encoded_name = quote(file_name)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=utf-8''{encoded_name}"},
    )


@router.get("/projects/{project_id}/rectifications/{item_id}", response_model=RectificationRead)
def get_rectification(project_id: int, item_id: int, db: Session = Depends(get_db)) -> RectificationRead:
    item = _get_item_or_404(db, project_id, item_id)
    return _read_item(item, db)


@router.patch("/projects/{project_id}/rectifications/{item_id}", response_model=RectificationRead)
def update_rectification(project_id: int, item_id: int, payload: RectificationUpdate, db: Session = Depends(get_db)) -> RectificationRead:
    item = _get_item_or_404(db, project_id, item_id)
    before = item.status
    changed: list[str] = []
    for field, value in payload.model_dump(exclude_unset=True).items():
        if getattr(item, field) != value:
            changed.append(_field_label(field))
            setattr(item, field, value)
    _apply_closed_at(item, before)
    if changed:
        action = "status_change" if "状态" in changed and len(changed) == 1 else "update"
        _add_log(db, item, action, before, item.status, f"更新：{'、'.join(changed)}")
    db.commit()
    db.refresh(item)
    return _read_item(item, db)


@router.post("/projects/{project_id}/rectifications/{item_id}/status", response_model=RectificationRead)
def change_status(project_id: int, item_id: int, payload: RectificationStatusUpdate, db: Session = Depends(get_db)) -> RectificationRead:
    item = _get_item_or_404(db, project_id, item_id)
    before = item.status
    item.status = payload.status
    if payload.remark:
        item.remark = payload.remark
    _apply_closed_at(item, before)
    action = "close" if payload.status == "closed" else "ignore" if payload.status == "ignored" else "status_change"
    _add_log(db, item, action, before, item.status, payload.remark or "状态变更")
    db.commit()
    db.refresh(item)
    return _read_item(item, db)


@router.post("/projects/{project_id}/rectifications/{item_id}/close", response_model=RectificationRead)
def close_rectification(project_id: int, item_id: int, db: Session = Depends(get_db)) -> RectificationRead:
    return change_status(project_id, item_id, RectificationStatusUpdate(status="closed"), db)


@router.get("/projects/{project_id}/rectifications/{item_id}/logs", response_model=list[RectificationActionLogRead])
def list_logs(project_id: int, item_id: int, db: Session = Depends(get_db)) -> list[RectificationActionLogRead]:
    _get_item_or_404(db, project_id, item_id)
    logs = db.execute(
        select(RectificationActionLog)
        .where(RectificationActionLog.project_id == project_id, RectificationActionLog.rectification_item_id == item_id)
        .order_by(RectificationActionLog.created_at.desc(), RectificationActionLog.id.desc())
    ).scalars()
    return [_read_log(log) for log in logs]


def _filtered_statement(project_id: int, **filters):
    statement = select(RectificationItem).where(RectificationItem.project_id == project_id)
    if filters.get("batch_ids"):
        statement = statement.where(RectificationItem.batch_id.in_(filters["batch_ids"]))
    elif filters.get("batch_id") is not None:
        statement = statement.where(RectificationItem.batch_id == filters["batch_id"])
    status_filter = filters.get("status_filter")
    if status_filter:
        statuses = [value.strip() for value in status_filter.split(",") if value.strip()]
        if statuses:
            statement = statement.where(RectificationItem.status.in_(statuses))
    for field in ("delay_level", "discipline", "building", "floor", "responsible_person", "responsible_unit", "source_type"):
        if filters.get(field):
            statement = statement.where(getattr(RectificationItem, field) == filters[field])
    if filters.get("overdue") is not None:
        condition = and_(RectificationItem.planned_finish_date < date.today(), RectificationItem.status.notin_(CLOSED_STATUSES))
        statement = statement.where(condition if filters["overdue"] else ~condition)
    if filters.get("keyword"):
        pattern = f"%{filters['keyword']}%"
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
    return statement


def _resolve_scope_batch_ids(
    db: Session,
    project_id: int,
    scope: str | None,
    batch_id: int | None,
    data_date: date | None,
    import_group_id: str | None,
    batch_ids: str | None,
) -> list[int] | None:
    if (scope or "").strip().lower() != "project":
        return None
    parsed_batch_ids = _parse_batch_ids(batch_ids)
    statement = select(ImportBatch.id).where(
        ImportBatch.project_id == project_id,
        ImportBatch.is_active.is_(True),
        ImportBatch.status == "published",
    )
    if import_group_id:
        statement = statement.where(ImportBatch.import_group_id == import_group_id)
    elif parsed_batch_ids:
        statement = statement.where(ImportBatch.id.in_(parsed_batch_ids))
    elif data_date is not None:
        statement = statement.where(ImportBatch.data_date == data_date)
    elif batch_id is not None:
        statement = statement.where(ImportBatch.id == batch_id)
    return list(db.scalars(statement.order_by(ImportBatch.id.asc())))


def _parse_batch_ids(value: str | None) -> list[int]:
    if not value:
        return []
    ids: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="batch_ids 参数格式不正确。") from exc
    return list(dict.fromkeys(ids))


def _apply_sort(statement, sort_by: str | None, sort_order: str):
    direction = sort_order.lower()
    sort_columns = {
        "created_at": RectificationItem.created_at,
        "updated_at": RectificationItem.updated_at,
        "planned_finish_date": RectificationItem.planned_finish_date,
        "progress_deviation": RectificationItem.progress_deviation,
        "delay_level": RectificationItem.delay_level,
        "status": RectificationItem.status,
    }
    if sort_by in sort_columns:
        column = sort_columns[sort_by]
        return statement.order_by(column.asc().nullslast() if direction == "asc" else column.desc().nullslast(), RectificationItem.id.desc())
    open_priority = case((RectificationItem.status.in_(FINAL_STATUSES), 1), else_=0)
    overdue_priority = case((and_(RectificationItem.planned_finish_date < date.today(), RectificationItem.status.notin_(CLOSED_STATUSES)), 0), else_=1)
    delay_priority = case(
        (RectificationItem.delay_level.in_(["seriously_delayed", "seriously_delay", "critical"]), 0),
        (RectificationItem.delay_level == "delayed", 1),
        else_=2,
    )
    return statement.order_by(open_priority, overdue_priority, delay_priority, RectificationItem.created_at.desc(), RectificationItem.id.desc())


def _get_item_or_404(db: Session, project_id: int, item_id: int) -> RectificationItem:
    item = db.get(RectificationItem, item_id)
    if item is None or item.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rectification item not found")
    return item


def _read_item(item: RectificationItem, db: Session | None = None) -> RectificationRead:
    source_batch_label, source_baseline_plan_id, source_baseline_plan_name = _source_context(db, item)
    return RectificationRead(
        id=item.id,
        project_id=item.project_id,
        batch_id=item.batch_id,
        source_batch_label=source_batch_label,
        source_baseline_plan_id=source_baseline_plan_id,
        source_baseline_plan_name=source_baseline_plan_name,
        progress_item_id=item.progress_item_id,
        warning_record_id=item.warning_record_id,
        source_type=item.source_type,
        source_id=item.source_id,
        source_label=_source_label(item.source_type),
        discipline=item.discipline,
        building=item.building,
        floor=item.floor,
        system_name=item.system_name,
        task_name=item.task_name,
        issue_description=item.issue_description,
        delay_level=item.delay_level,
        delay_level_label=_delay_label(item.delay_level),
        actual_percent=item.actual_percent,
        planned_percent=item.planned_percent,
        progress_deviation=item.progress_deviation,
        responsible_person=item.responsible_person,
        responsible_unit=item.responsible_unit,
        planned_finish_date=item.planned_finish_date,
        status=item.status,
        status_label=_status_label(item.status),
        review_result=item.review_result,
        remark=item.remark,
        is_overdue=_is_overdue(item),
        created_at=item.created_at,
        updated_at=item.updated_at,
        closed_at=item.closed_at,
    )


def _source_context(db: Session | None, item: RectificationItem) -> tuple[str | None, int | None, str | None]:
    if db is None or item.batch_id is None:
        return None, None, None
    batch = db.get(ImportBatch, item.batch_id)
    if batch is None:
        return None, None, None
    batch_label = f"#{batch.id} / {batch.file_name}"
    if batch.data_date:
        batch_label = f"{batch_label} / {batch.data_date.isoformat()}"
    baseline_name = None
    if batch.baseline_plan_id is not None:
        baseline = db.get(BaselinePlan, batch.baseline_plan_id)
        if baseline is not None and baseline.project_id == item.project_id:
            baseline_name = baseline.name
    return batch_label, batch.baseline_plan_id, baseline_name


def _read_log(log: RectificationActionLog) -> RectificationActionLogRead:
    return RectificationActionLogRead(
        id=log.id,
        rectification_item_id=log.rectification_item_id,
        project_id=log.project_id,
        action=log.action,
        action_label=ACTION_LABELS.get(log.action, log.action),
        from_status=log.from_status,
        from_status_label=_status_label(log.from_status) if log.from_status else None,
        to_status=log.to_status,
        to_status_label=_status_label(log.to_status) if log.to_status else None,
        content=log.content,
        created_at=log.created_at,
    )


def _add_log(db: Session, item: RectificationItem, action: str, from_status: str | None, to_status: str | None, content: str | None) -> None:
    db.add(
        RectificationActionLog(
            rectification_item_id=item.id,
            project_id=item.project_id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            content=content,
        )
    )


def _add_export_logs(db: Session, items: list[RectificationItem], content: str) -> None:
    for item in items:
        _add_log(db, item, "export", item.status, item.status, content)


def _apply_closed_at(item: RectificationItem, before: str | None) -> None:
    if item.status == "closed" and before != "closed":
        item.closed_at = datetime.now()
    elif before == "closed" and item.status != "closed":
        item.closed_at = None


def _is_overdue(item: RectificationItem) -> bool:
    return bool(item.planned_finish_date and item.planned_finish_date < date.today() and item.status not in CLOSED_STATUSES)


def _week_start(value: datetime) -> datetime:
    today = value.date()
    start = today - timedelta(days=today.weekday())
    return datetime.combine(start, time.min)


def _progress_item_for_warning(db: Session, warning: WarningRecord) -> ProgressItem | None:
    if warning.task_id is None or warning.batch_id is None:
        return None
    return db.scalar(
        select(ProgressItem).where(
            ProgressItem.project_id == warning.project_id,
            ProgressItem.batch_id == warning.batch_id,
            ProgressItem.task_id == warning.task_id,
        )
    )


def _warning_delay_level(level: str | None) -> str:
    normalized = (level or "").lower()
    if normalized in {"critical", "serious", "high"}:
        return "seriously_delayed"
    if normalized in {"warning", "medium"}:
        return "delayed"
    return "slightly_delayed"


def _status_label(value: str | None) -> str:
    return STATUS_LABELS.get(value or "", value or "-")


def _delay_label(value: str | None) -> str:
    return DELAY_LABELS.get(value or "", value or "-")


def _source_label(value: str | None) -> str:
    return {"manual": "手动创建", "progress_item": "滞后项", "warning": "预警记录"}.get(value or "", value or "-")


def _field_label(field: str) -> str:
    labels = {
        "responsible_person": "责任人",
        "responsible_unit": "责任单位",
        "planned_finish_date": "计划完成时间",
        "status": "状态",
        "review_result": "复查结果",
        "remark": "备注",
    }
    return labels.get(field, field)


def _calculation_method_context(db: Session, project: Project, batch_id: int | None, calculation_method: str | None) -> dict[str, str]:
    batch = get_published_batch(db, project.id, batch_id)
    if batch is None:
        return {
            "label": "自动推荐",
            "reason": "-",
            "unit_mixed": "否",
            "units": "未识别",
            "weight_source": "未使用权重字段",
            "weight_sum": "-",
            "description": "-",
        }
    items = apply_time_based_progress(list_items(db, project.id, batch.id), batch)
    profile = resolve_calculation_profile(db, project.id, batch.calculation_profile_id)
    method = effective_calculation_method(project, calculation_method)
    stats = statistics_context(items, profile, method)
    units = item_units(items)
    return {
        "label": stats.label,
        "reason": stats.reason or "用户手动选择统计口径",
        "unit_mixed": "是" if len(units) > 1 else "否",
        "units": "、".join(units) or "未识别",
        "weight_source": stats.weight_source or "未使用权重字段",
        "weight_sum": f"{stats.weight_total:.4f}" if stats.weight_total is not None else "-",
        "description": stats.method_description or "-",
    }


def _fill_export_sheet(sheet, project: Project, batch_id: int | None, items: list[RectificationItem], filters: dict, db: Session, method_context: dict[str, str] | None = None) -> None:
    batch = db.get(ImportBatch, batch_id) if batch_id else None
    current_baseline_name = _baseline_name(db, project.id, filters.get("baseline_plan_id"))
    bound_baseline_name = _batch_baseline_name(db, batch) if batch else "未配置计划基线"
    consistent = (batch.baseline_plan_id if batch else None) == filters.get("baseline_plan_id")
    if filters.get("baseline_plan_id") is None:
        consistent = batch is None or batch.baseline_plan_id is None
    sheet.append(["整改跟踪表"])
    sheet.append(["项目名称", project.name])
    sheet.append(["数据日期", batch.data_date.isoformat() if batch and batch.data_date else "全部"])
    if method_context:
        sheet.append(["当前统计口径", method_context["label"]])
        sheet.append(["推荐原因", method_context["reason"]])
        sheet.append(["是否混合单位", method_context["unit_mixed"]])
        sheet.append(["单位列表", method_context["units"]])
        sheet.append(["权重来源", method_context["weight_source"]])
        sheet.append(["当前范围权重合计", method_context["weight_sum"]])
        sheet.append(["统计口径说明", method_context["description"]])
    sheet.append(["批次绑定计划基线", bound_baseline_name])
    sheet.append(["当前查看计划基线", current_baseline_name or bound_baseline_name])
    sheet.append(["是否与批次绑定基线一致", "是" if consistent else "否"])
    if not consistent:
        sheet.append(["基线提示", "本报表当前查看基线与批次绑定基线不同，请注意分析口径。"])
    sheet.append(["筛选状态", filters.get("status") or "全部"])
    sheet.append(["筛选专业", filters.get("discipline") or "全部"])
    sheet.append(["筛选楼栋", filters.get("building") or "全部"])
    sheet.append(["筛选楼层", filters.get("floor") or "全部"])
    sheet.append(["筛选责任人", filters.get("responsible_person") or "全部"])
    sheet.append(["是否逾期", "全部" if filters.get("overdue") is None else "是" if filters.get("overdue") else "否"])
    sheet.append(["导出时间", datetime.now().strftime("%Y-%m-%d %H:%M")])
    sheet.append([])
    sheet.append([
        "状态",
        "滞后等级",
        "专业",
        "楼栋",
        "楼层",
        "系统",
        "施工项",
        "问题描述",
        "责任人",
        "责任单位",
        "计划完成时间",
        "是否逾期",
        "复查结果",
        "备注",
        "整改记录摘要",
        "最近更新时间",
        "来源类型",
        "来源 ID",
        "来源计划基线",
        "创建时间",
        "关闭时间",
    ])
    for item in items:
        sheet.append([
            _status_label(item.status),
            _delay_label(item.delay_level),
            display_text(item.discipline, "未填写专业"),
            display_text(item.building, "未填写楼栋"),
            display_text(item.floor, "未填写楼层"),
            display_text(item.system_name, "未填写系统"),
            display_text(item.task_name, "未填写施工项"),
            item.issue_description or "",
            item.responsible_person or "",
            item.responsible_unit or "",
            item.planned_finish_date.isoformat() if item.planned_finish_date else "",
            "是" if _is_overdue(item) else "否",
            item.review_result or "",
            item.remark or "",
            _log_summary(db, item.id),
            item.updated_at.strftime("%Y-%m-%d %H:%M") if item.updated_at else "",
            item.source_type,
            item.source_id,
            _rectification_baseline_name(db, item),
            item.created_at.strftime("%Y-%m-%d %H:%M") if item.created_at else "",
            item.closed_at.strftime("%Y-%m-%d %H:%M") if item.closed_at else "",
        ])


def _log_summary(db: Session, item_id: int) -> str:
    logs = db.execute(
        select(RectificationActionLog)
        .where(RectificationActionLog.rectification_item_id == item_id)
        .order_by(RectificationActionLog.created_at.desc(), RectificationActionLog.id.desc())
        .limit(3)
    ).scalars()
    return "；".join(f"{ACTION_LABELS.get(log.action, log.action)}：{log.content or ''}" for log in logs)


def _batch_baseline_name(db: Session, batch: ImportBatch | None) -> str:
    if batch is None or batch.baseline_plan_id is None:
        return "未配置计划基线"
    baseline = db.get(BaselinePlan, batch.baseline_plan_id)
    if baseline is None or baseline.project_id != batch.project_id:
        return "未配置计划基线"
    return baseline.name


def _baseline_name(db: Session, project_id: int, baseline_plan_id: int | None) -> str | None:
    if baseline_plan_id is None:
        return None
    baseline = db.get(BaselinePlan, baseline_plan_id)
    if baseline is None or baseline.project_id != project_id:
        return None
    return baseline.name


def _rectification_baseline_name(db: Session, item: RectificationItem) -> str:
    if item.batch_id is None:
        return "未配置计划基线"
    return _batch_baseline_name(db, db.get(ImportBatch, item.batch_id))
