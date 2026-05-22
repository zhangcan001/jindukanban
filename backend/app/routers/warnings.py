from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.import_batch import ImportBatch
from app.models.progress_item import ProgressItem
from app.models.project import Project
from app.models.rectification_item import RectificationItem
from app.models.warning_record import WarningRecord
from app.models.warning_rule import WarningRule
from app.schemas.warning import (
    WarningFilterOptions,
    WarningRecordRead,
    WarningRuleCreate,
    WarningRuleRead,
    WarningRuleUpdate,
    WarningRunResponse,
)
from app.services.warning_service import DATA_QUALITY_WARNING_RULE_TYPE, ensure_builtin_warning_rules, is_data_quality_warning_record, run_warning_rules

router = APIRouter(tags=["warnings"])


def get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前项目不存在或已被清理。")
    return project


def get_rule_or_404(rule_id: int, db: Session) -> WarningRule:
    rule = db.get(WarningRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warning rule not found")
    return rule


def get_published_batch(project_id: int, batch_id: int | None, db: Session) -> ImportBatch:
    statement = select(ImportBatch).where(ImportBatch.project_id == project_id, ImportBatch.status == "published", ImportBatch.is_active.is_(True))
    if batch_id is not None:
        statement = statement.where(ImportBatch.id == batch_id)
    else:
        statement = statement.order_by(ImportBatch.data_date.desc().nullslast(), ImportBatch.published_at.desc().nullslast(), ImportBatch.id.desc())
    batch = db.execute(statement).scalars().first()
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Published import batch not found")
    return batch


@router.get("/projects/{project_id}/warning-rules", response_model=list[WarningRuleRead])
def list_warning_rules(project_id: int, db: Session = Depends(get_db)) -> list[WarningRule]:
    get_project_or_404(project_id, db)
    ensure_builtin_warning_rules(db, project_id)
    db.commit()
    return list(
        db.execute(
            select(WarningRule)
            .where(WarningRule.project_id == project_id, WarningRule.rule_type != DATA_QUALITY_WARNING_RULE_TYPE)
            .order_by(WarningRule.id)
        ).scalars()
    )


@router.post("/projects/{project_id}/warning-rules", response_model=WarningRuleRead, status_code=status.HTTP_201_CREATED)
def create_warning_rule(project_id: int, payload: WarningRuleCreate, db: Session = Depends(get_db)) -> WarningRule:
    get_project_or_404(project_id, db)
    if payload.rule_type == DATA_QUALITY_WARNING_RULE_TYPE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="数据质量评分低属于批次质量提示，不再作为预警记录规则。")
    rule = WarningRule(project_id=project_id, **payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.put("/warning-rules/{rule_id}", response_model=WarningRuleRead)
def update_warning_rule(rule_id: int, payload: WarningRuleUpdate, db: Session = Depends(get_db)) -> WarningRule:
    rule = get_rule_or_404(rule_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/warning-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_warning_rule(rule_id: int, db: Session = Depends(get_db)) -> None:
    rule = get_rule_or_404(rule_id, db)
    db.delete(rule)
    db.commit()


@router.post("/projects/{project_id}/warnings/run", response_model=WarningRunResponse)
def run_warnings(project_id: int, batch_id: int | None = None, db: Session = Depends(get_db)) -> WarningRunResponse:
    get_project_or_404(project_id, db)
    batch = get_published_batch(project_id, batch_id, db)
    records = run_warning_rules(db, project_id, batch)
    db.commit()
    for record in records:
        db.refresh(record)
    enriched_records = _query_warning_records(db, project_id=project_id, batch_id=batch.id)
    return WarningRunResponse(batch_id=batch.id, generated_count=len(records), records=enriched_records)


@router.get("/projects/{project_id}/warnings", response_model=list[WarningRecordRead])
def list_warnings(
    project_id: int,
    batch_id: int | None = None,
    unresolved_only: bool = Query(False),
    discipline: str | None = None,
    building: str | None = None,
    floor: str | None = None,
    level: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = None,
    db: Session = Depends(get_db),
) -> list[WarningRecordRead]:
    get_project_or_404(project_id, db)
    return _query_warning_records(
        db,
        project_id=project_id,
        batch_id=batch_id,
        unresolved_only=unresolved_only,
        discipline=discipline,
        building=building,
        floor=floor,
        level=level,
        status_filter=status_filter,
        keyword=keyword,
    )


@router.get("/projects/{project_id}/warnings/filter-options", response_model=WarningFilterOptions)
def list_warning_filter_options(
    project_id: int,
    batch_id: int | None = None,
    db: Session = Depends(get_db),
) -> WarningFilterOptions:
    """返回当前批次预警记录的专业/楼栋/楼层下拉选项。

    存在的理由:前端原来在 loadOptionRecords 里把全部预警记录拉回来,在浏览器里
    distinct 出专业/楼栋/楼层,而且每次改筛选条件后还会重复拉一次。这里改成一条
    JOIN + DISTINCT 的 SQL。预警维度来自 ProgressItem(预警表本身不存这些列),
    INNER JOIN 自然把没有关联进度行的"数据质量"类预警排除掉——与列表里的下拉口径一致。
    """
    get_project_or_404(project_id, db)
    statement = (
        select(ProgressItem.discipline, ProgressItem.building, ProgressItem.floor)
        .join(
            WarningRecord,
            and_(
                ProgressItem.project_id == WarningRecord.project_id,
                ProgressItem.batch_id == WarningRecord.batch_id,
                ProgressItem.task_id == WarningRecord.task_id,
            ),
        )
        .where(WarningRecord.project_id == project_id)
        .distinct()
    )
    if batch_id is not None:
        statement = statement.where(WarningRecord.batch_id == batch_id)

    disciplines: set[str] = set()
    buildings: set[str] = set()
    floors: set[str] = set()
    floors_by_building: dict[str, set[str]] = {}
    for discipline, building, floor in db.execute(statement):
        if discipline:
            disciplines.add(discipline)
        if building:
            buildings.add(building)
        if floor:
            floors.add(floor)
        if building and floor:
            floors_by_building.setdefault(building, set()).add(floor)

    return WarningFilterOptions(
        disciplines=sorted(disciplines),
        buildings=sorted(buildings),
        floors=sorted(floors),
        floors_by_building={k: sorted(v) for k, v in floors_by_building.items()},
    )


@router.get("/projects/{project_id}/warnings/export")
def export_warnings(
    project_id: int,
    batch_id: int | None = None,
    unresolved_only: bool = Query(False),
    discipline: str | None = None,
    building: str | None = None,
    floor: str | None = None,
    level: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = None,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    get_project_or_404(project_id, db)
    records = _query_warning_records(
        db,
        project_id=project_id,
        batch_id=batch_id,
        unresolved_only=unresolved_only,
        discipline=discipline,
        building=building,
        floor=floor,
        level=level,
        status_filter=status_filter,
        keyword=keyword,
    )
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "预警记录"
    headers = [
        "预警级别",
        "处理状态",
        "专业",
        "楼栋",
        "楼层",
        "系统",
        "施工项",
        "实际完成率",
        "计划完成率",
        "进度偏差",
        "预警规则",
        "预警说明",
        "触发时间",
        "处理备注",
    ]
    sheet.append(headers)
    for record in records:
        sheet.append(
            [
                record.level_label,
                record.status_label,
                record.discipline,
                record.building,
                record.floor,
                record.system_name,
                record.task_name,
                _percent_text(record.actual_percent),
                _percent_text(record.planned_percent),
                _percent_text(record.progress_deviation),
                record.rule_name or "-",
                record.warning_message,
                record.created_at.strftime("%Y-%m-%d %H:%M"),
                record.remark or "-",
            ]
        )
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    filename = f"warnings_{project_id}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _query_warning_records(
    db: Session,
    project_id: int,
    batch_id: int | None = None,
    unresolved_only: bool = False,
    discipline: str | None = None,
    building: str | None = None,
    floor: str | None = None,
    level: str | None = None,
    status_filter: str | None = None,
    keyword: str | None = None,
) -> list[WarningRecordRead]:
    join_condition = and_(
        ProgressItem.project_id == WarningRecord.project_id,
        ProgressItem.batch_id == WarningRecord.batch_id,
        ProgressItem.task_id == WarningRecord.task_id,
    )
    statement = (
        select(WarningRecord, ProgressItem, WarningRule)
        .outerjoin(ProgressItem, join_condition)
        .outerjoin(WarningRule, WarningRule.id == WarningRecord.rule_id)
        .where(WarningRecord.project_id == project_id)
    )
    if batch_id is not None:
        statement = statement.where(WarningRecord.batch_id == batch_id)
    if unresolved_only:
        statement = statement.where(WarningRecord.is_resolved.is_(False))
    if level:
        statement = statement.where(WarningRecord.level == level)
    if status_filter in {"open", "unhandled"}:
        statement = statement.where(WarningRecord.is_resolved.is_(False))
    elif status_filter in {"handled", "ignored"}:
        statement = statement.where(WarningRecord.is_resolved.is_(True))
    if discipline:
        statement = statement.where(ProgressItem.discipline == discipline)
    if building:
        statement = statement.where(ProgressItem.building == building)
    if floor:
        statement = statement.where(ProgressItem.floor == floor)
    if keyword:
        keyword_pattern = f"%{keyword}%"
        statement = statement.where(
            or_(
                ProgressItem.task_name.ilike(keyword_pattern),
                WarningRecord.message.ilike(keyword_pattern),
                WarningRecord.title.ilike(keyword_pattern),
            )
        )
    rows = db.execute(statement.order_by(WarningRecord.created_at.desc(), WarningRecord.id.desc())).all()
    rectification_rows = db.execute(
        select(RectificationItem.warning_record_id, RectificationItem.id).where(
            RectificationItem.project_id == project_id,
            RectificationItem.warning_record_id.is_not(None),
            RectificationItem.source_type == "warning",
        )
    ).all()
    rectification_by_warning = {warning_id: rectification_id for warning_id, rectification_id in rectification_rows}
    seen: set[int] = set()
    records: list[WarningRecordRead] = []
    for record, item, rule in rows:
        if is_data_quality_warning_record(record, rule):
            continue
        if record.id in seen:
            continue
        seen.add(record.id)
        setattr(record, "_rectification_item_id", rectification_by_warning.get(record.id))
        records.append(_build_warning_read(record, item, rule))
    return records


def _build_warning_read(
    record: WarningRecord,
    item: ProgressItem | None,
    rule: WarningRule | None,
) -> WarningRecordRead:
    warning_message = _warning_message(record, item)
    is_resolved = bool(record.is_resolved)
    return WarningRecordRead(
        id=record.id,
        project_id=record.project_id,
        batch_id=record.batch_id,
        progress_item_id=item.id if item else None,
        task_id=record.task_id,
        rule_id=record.rule_id,
        rule_name=rule.name if rule else None,
        level=record.level,
        level_label=_level_label(record.level),
        status="handled" if is_resolved else "open",
        status_label="已处理" if is_resolved else "未处理",
        title=record.title,
        message=record.message,
        warning_message=warning_message,
        task_name=_field_or_placeholder(item.task_name if item else None, "未填写施工项"),
        discipline=_field_or_placeholder(item.discipline if item else None, "未填写专业"),
        building=_field_or_placeholder(item.building if item else None, "未填写楼栋"),
        floor=_field_or_placeholder(item.floor if item else None, "未填写楼层"),
        system_name=_field_or_placeholder(item.system_name if item else None, "未填写系统"),
        unit=item.unit if item else None,
        actual_percent=item.actual_percent if item else None,
        planned_percent=item.planned_percent if item else None,
        progress_deviation=item.progress_deviation if item else None,
        is_resolved=is_resolved,
        created_at=record.created_at,
        handled_at=None,
        remark=None,
        rectification_item_id=getattr(record, "_rectification_item_id", None),
        has_rectification=bool(getattr(record, "_rectification_item_id", None)),
    )


def _warning_message(record: WarningRecord, item: ProgressItem | None) -> str:
    message = record.message or ""
    if item is None:
        return message or record.title or "-"
    context = _item_context(item)
    if _message_has_context(message, item):
        return message
    if item.planned_percent is None:
        return f"{context}：当前实际完成 {_percent_text(item.actual_percent)}，缺少计划进度字段，无法判断计划偏差。"
    if item.progress_deviation is not None and item.progress_deviation < 0:
        return (
            f"{context}：实际完成 {_percent_text(item.actual_percent)}，计划完成 {_percent_text(item.planned_percent)}，"
            f"滞后 {_number_text(abs(item.progress_deviation))} 个百分点，触发{_level_label(record.level)}。"
        )
    return f"{context}：{message or record.title or '触发预警。'}"


def _item_context(item: ProgressItem) -> str:
    discipline = _field_or_placeholder(item.discipline, "未填写专业")
    building = _field_or_placeholder(item.building, "未填写楼栋")
    floor = _field_or_placeholder(item.floor, "未填写楼层")
    system_name = _field_or_placeholder(item.system_name, "未填写系统")
    task_name = _field_or_placeholder(item.task_name, "未填写施工项")
    return f"【{discipline}】{building} {floor} {system_name} {task_name}"


def _message_has_context(message: str, item: ProgressItem) -> bool:
    parts = [item.building, item.floor, item.system_name, item.task_name]
    return bool(message) and any(part and part.strip() and part.strip() in message for part in parts)


def _field_or_placeholder(value: str | None, placeholder: str) -> str:
    return value.strip() if value and value.strip() else placeholder


def _level_label(level: str | None) -> str:
    normalized = (level or "").lower()
    if normalized in {"serious", "critical", "high"}:
        return "严重预警"
    if normalized in {"warning", "medium"}:
        return "一般预警"
    if normalized in {"info", "low"}:
        return "提示"
    return "一般预警"


def _percent_text(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1f}%"


def _number_text(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1f}"
