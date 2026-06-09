from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.calculation_profile import CalculationProfile
from app.models.import_batch import ImportBatch
from app.models.progress_item import ProgressItem
from app.models.progress_item_edit_history import ProgressItemEditHistory
from app.models.project import Project
from app.schemas.progress_item import (
    ProgressItemEditHistoryRead,
    ProgressItemFilterOptions,
    ProgressItemListResponse,
    ProgressItemRead,
    ProgressItemScopeInfo,
    ProgressItemUpdate,
)
from app.services.analytics_service import apply_time_based_progress, get_published_batch, list_items
from app.services.progress_calculator import calculate_progress_fields

router = APIRouter(tags=["progress items"])

EDITABLE_FIELDS = {
    "actual_quantity",
    "cumulative_quantity",
    "period_quantity",
    "planned_quantity",
    "total_quantity",
    "actual_percent",
    "planned_percent",
    "reported_percent",
    "remaining_quantity",
    "planned_start_date",
    "planned_finish_date",
    "actual_start_date",
    "actual_finish_date",
    "weight",
    "value_amount",
    "status",
    "remark",
}

CALCULATED_FIELDS = {
    "actual_percent",
    "planned_percent",
    "imported_planned_percent",
    "time_planned_percent",
    "remaining_quantity",
    "progress_deviation",
    "status",
    "schedule_phase",
    "current_period_quantity",
    "current_period_percent",
}


@router.get("/projects/{project_id}/items", response_model=ProgressItemListResponse)
@router.get("/projects/{project_id}/progress-items", response_model=ProgressItemListResponse)
def list_progress_items(
    project_id: int,
    scope: str | None = None,
    batch_id: int | None = None,
    data_date: date | None = None,
    import_group_id: str | None = None,
    batch_ids: str | None = None,
    construction_unit: str | None = None,
    building: str | None = None,
    floor: str | None = None,
    discipline: str | None = None,
    system_name: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ProgressItemListResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前项目不存在或已被清理。")

    batches, scope_info = _resolve_progress_item_scope(
        db,
        project_id,
        scope,
        batch_id,
        data_date,
        import_group_id,
        batch_ids,
    )
    if not batches:
        return ProgressItemListResponse(items=[], total=0, page=page, page_size=page_size, scope_info=scope_info)

    included_batch_ids = [batch.id for batch in batches]
    base = select(ProgressItem).where(ProgressItem.project_id == project_id, ProgressItem.batch_id.in_(included_batch_ids))
    if construction_unit:
        base = base.where(ProgressItem.construction_unit == construction_unit)
    if building:
        base = base.where(ProgressItem.building == building)
    if floor:
        base = base.where(ProgressItem.floor == floor)
    if discipline:
        base = base.where(ProgressItem.discipline == discipline)
    if system_name:
        base = base.where(ProgressItem.system_name == system_name)
    if status:
        status_values = _status_filter_values(status)
        base = base.where(ProgressItem.status.in_(status_values) if len(status_values) > 1 else ProgressItem.status == status_values[0])
    if keyword:
        like_keyword = f"%{keyword.strip()}%"
        base = base.where(
            ProgressItem.task_name.ilike(like_keyword)
            | ProgressItem.task_code.ilike(like_keyword)
            | ProgressItem.wbs_code.ilike(like_keyword)
            | ProgressItem.construction_unit.ilike(like_keyword)
            | ProgressItem.system_name.ilike(like_keyword)
            | ProgressItem.remark.ilike(like_keyword)
        )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = list(
        db.execute(
            base.order_by(ProgressItem.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).scalars()
    )
    adjusted_items: list[ProgressItem] = []
    for current_batch in batches:
        batch_items = [item for item in items if item.batch_id == current_batch.id]
        adjusted_items.extend(apply_time_based_progress(batch_items, current_batch))
    adjusted_items.sort(key=lambda item: item.id)
    scope_info.task_count = total
    return ProgressItemListResponse(items=adjusted_items, total=total, page=page, page_size=page_size, scope_info=scope_info)


@router.get("/projects/{project_id}/progress-items/filter-options", response_model=ProgressItemFilterOptions)
def list_progress_item_filter_options(
    project_id: int,
    scope: str | None = None,
    batch_id: int | None = None,
    data_date: date | None = None,
    import_group_id: str | None = None,
    batch_ids: str | None = None,
    db: Session = Depends(get_db),
) -> ProgressItemFilterOptions:
    """返回当前 scope 下的筛选下拉选项。

    存在的理由:前端原来要拉光所有 ProgressItem(while True 翻 200 条/页)只为 distinct 出
    施工单位/楼栋/楼层/专业/系统/状态六列文本。批次稍大就要几次顺序 HTTP,切换批次卡顿。
    这里改成一次 SQL DISTINCT。
    """
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前项目不存在或已被清理。")

    batches, _ = _resolve_progress_item_scope(
        db,
        project_id,
        scope,
        batch_id,
        data_date,
        import_group_id,
        batch_ids,
    )
    if not batches:
        return ProgressItemFilterOptions()

    included_batch_ids = [batch.id for batch in batches]
    rows = list(
        db.execute(
            select(
                ProgressItem.construction_unit,
                ProgressItem.building,
                ProgressItem.floor,
                ProgressItem.discipline,
                ProgressItem.system_name,
                ProgressItem.status,
            )
            .where(
                ProgressItem.project_id == project_id,
                ProgressItem.batch_id.in_(included_batch_ids),
            )
            .distinct()
        )
    )

    construction_units: set[str] = set()
    buildings: set[str] = set()
    floors: set[str] = set()
    disciplines: set[str] = set()
    system_names: set[str] = set()
    statuses: set[str] = set()
    floors_by_building: dict[str, set[str]] = {}

    for cu, bld, flr, disc, sysn, st in rows:
        if cu:
            construction_units.add(cu)
        if bld:
            buildings.add(bld)
        if flr:
            floors.add(flr)
        if disc:
            disciplines.add(disc)
        if sysn:
            system_names.add(sysn)
        if st:
            statuses.add(st)
        if bld and flr:
            floors_by_building.setdefault(bld, set()).add(flr)

    return ProgressItemFilterOptions(
        construction_units=sorted(construction_units),
        buildings=sorted(buildings),
        floors=sorted(floors),
        disciplines=sorted(disciplines),
        system_names=sorted(system_names),
        statuses=sorted(statuses),
        floors_by_building={k: sorted(v) for k, v in floors_by_building.items()},
    )


@router.put("/progress-items/{item_id}", response_model=ProgressItemRead)
def update_progress_item(
    item_id: int,
    payload: ProgressItemUpdate,
    db: Session = Depends(get_db),
) -> ProgressItem:
    item = db.get(ProgressItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Progress item not found")
    if not payload.reason.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Edit reason is required")

    batch = db.get(ImportBatch, item.batch_id)
    if batch is not None and batch.is_frozen:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="冻结批次禁止修改人工修正，请先取消冻结。")
    profile = db.get(CalculationProfile, batch.calculation_profile_id) if batch and batch.calculation_profile_id else None
    previous_item = _find_previous_item(db, item, batch)
    changed_fields: set[str] = set()
    update_data = payload.model_dump(exclude_unset=True)
    reason = update_data.pop("reason")
    # 同一次 PUT 产生的所有历史行共享一个 session id,撤销时按它分组——比按 reason
    # 字符串 + 2 秒 edited_at 窗口那套近似算法可靠得多
    session_id = uuid.uuid4().hex

    for field, value in update_data.items():
        if field not in EDITABLE_FIELDS:
            continue
        old_value = getattr(item, field)
        if _value_text(old_value) == _value_text(value):
            continue
        setattr(item, field, value)
        changed_fields.add(field)
        db.add(
            ProgressItemEditHistory(
                progress_item_id=item.id,
                field_name=field,
                old_value=_value_text(old_value),
                new_value=_value_text(value),
                reason=reason,
                edited_by="system",
                edit_session_id=session_id,
            )
        )

    if changed_fields:
        values = {field: getattr(item, field) for field in _progress_value_fields()}
        _prefer_recalculation_for_manual_edit(values, changed_fields)
        calculated = calculate_progress_fields(values, profile, batch.data_date if batch else None, previous_item)
        for field in CALCULATED_FIELDS:
            old_value = getattr(item, field)
            new_value = calculated.get(field)
            if _value_text(old_value) == _value_text(new_value):
                continue
            setattr(item, field, new_value)
            if field not in changed_fields:
                db.add(
                    ProgressItemEditHistory(
                        progress_item_id=item.id,
                        field_name=field,
                        old_value=_value_text(old_value),
                        new_value=_value_text(new_value),
                        reason=f"系统重算：{reason}",
                        edited_by="system",
                        edit_session_id=session_id,
                    )
                )
        item.is_manually_edited = True
        item.manual_edit_reason = reason

    db.commit()
    db.refresh(item)
    return item


@router.get("/progress-items/{item_id}/edit-history", response_model=list[ProgressItemEditHistoryRead])
def get_edit_history(item_id: int, db: Session = Depends(get_db)) -> list[ProgressItemEditHistory]:
    item = db.get(ProgressItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Progress item not found")
    return list(
        db.execute(
            select(ProgressItemEditHistory)
            .where(ProgressItemEditHistory.progress_item_id == item_id)
            .order_by(ProgressItemEditHistory.edited_at.desc(), ProgressItemEditHistory.id.desc())
        ).scalars()
    )


# 撤销最近一次"用户修改 + 系统重算"的整组历史。
# update_progress_item 会为同一次操作写多条 ProgressItemEditHistory(用户改的字段 +
# 系统重算的字段),它们共享同一个 reason 文案("xxx" 或 "系统重算：xxx"),按 reason
# 字符串去掉前缀做分组即可识别"一组"。
_DATE_REVERT_FIELDS = {
    "planned_start_date",
    "planned_finish_date",
    "actual_start_date",
    "actual_finish_date",
}
_FLOAT_REVERT_FIELDS = {
    "actual_quantity",
    "cumulative_quantity",
    "period_quantity",
    "planned_quantity",
    "total_quantity",
    "actual_percent",
    "planned_percent",
    "reported_percent",
    "remaining_quantity",
    "weight",
    "value_amount",
    "imported_planned_percent",
    "time_planned_percent",
    "progress_deviation",
    "current_period_quantity",
    "current_period_percent",
}


def _revert_history_value(field_name: str, text_value: str | None) -> Any:
    if text_value is None or text_value == "":
        return None
    if field_name in _DATE_REVERT_FIELDS:
        try:
            return date.fromisoformat(text_value)
        except ValueError:
            return None
    if field_name in _FLOAT_REVERT_FIELDS:
        try:
            return float(text_value)
        except ValueError:
            return None
    return text_value


@router.post("/progress-items/{item_id}/undo-last-edit", response_model=ProgressItemRead)
def undo_last_edit(item_id: int, db: Session = Depends(get_db)) -> ProgressItem:
    """撤销该明细行最近一次"用户修改 + 系统重算"的整组改动。

    给值班一线工程师一个"刚才那次手改不对,撤回"的安全网——之前要么用户得拼命回忆原值
    再 PUT 一次,要么只能去翻 edit_history 表手动 SQL,体验非常糟。
    """
    item = db.get(ProgressItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Progress item not found")
    batch = db.get(ImportBatch, item.batch_id)
    if batch is not None and batch.is_frozen:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="冻结批次禁止撤销,请先取消冻结。")

    # 排除 __undo__ 审计行,否则连续两次撤销时第二次会误把上次的审计行当成"最近一次修改"
    # 排除 __undo__ 审计行,否则连续两次撤销时第二次会误把上次的审计行当成"最近一次修改"
    latest_entry = db.execute(
        select(ProgressItemEditHistory)
        .where(
            ProgressItemEditHistory.progress_item_id == item_id,
            ProgressItemEditHistory.field_name != "__undo__",
        )
        .order_by(ProgressItemEditHistory.edited_at.desc(), ProgressItemEditHistory.id.desc())
    ).scalars().first()
    if latest_entry is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该明细暂无可撤销的修改。")

    # 优先按 edit_session_id 分组——这是 2026-05 之后的新数据的事实依据。
    # 旧数据 edit_session_id=NULL,回退到"按 reason 字符串 + 2 秒窗口"近似算法保留兼容性。
    if latest_entry.edit_session_id:
        window_entries = list(
            db.execute(
                select(ProgressItemEditHistory)
                .where(
                    ProgressItemEditHistory.progress_item_id == item_id,
                    ProgressItemEditHistory.edit_session_id == latest_entry.edit_session_id,
                    ProgressItemEditHistory.field_name != "__undo__",
                )
                .order_by(ProgressItemEditHistory.id.desc())
            ).scalars()
        )
        base_reason = (latest_entry.reason or "").removeprefix("系统重算：")
    else:
        base_reason = (latest_entry.reason or "").removeprefix("系统重算：")
        group_entries = list(
            db.execute(
                select(ProgressItemEditHistory)
                .where(
                    ProgressItemEditHistory.progress_item_id == item_id,
                    ProgressItemEditHistory.field_name != "__undo__",
                    (ProgressItemEditHistory.reason == base_reason)
                    | (ProgressItemEditHistory.reason == f"系统重算：{base_reason}"),
                )
                .order_by(ProgressItemEditHistory.id.desc())
            ).scalars()
        )
        if not group_entries:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该明细暂无可撤销的修改。")
        latest_ts = group_entries[0].edited_at
        window_entries = [e for e in group_entries if abs((e.edited_at - latest_ts).total_seconds()) <= 2]

    for entry in window_entries:
        if entry.field_name not in EDITABLE_FIELDS and entry.field_name not in CALCULATED_FIELDS:
            continue
        old_value = _revert_history_value(entry.field_name, entry.old_value)
        setattr(item, entry.field_name, old_value)

    # 写一条 "撤销" 历史,方便审计——但不再触发递归撤销
    db.add(
        ProgressItemEditHistory(
            progress_item_id=item.id,
            field_name="__undo__",
            old_value=None,
            new_value=None,
            reason=f"撤销操作：{base_reason}",
            edited_by="system",
        )
    )

    # 如果撤销后没有任何更早的非 "__undo__" 历史,则把 is_manually_edited 清掉
    remaining_edits = db.execute(
        select(func.count(ProgressItemEditHistory.id)).where(
            ProgressItemEditHistory.progress_item_id == item.id,
            ProgressItemEditHistory.field_name != "__undo__",
            ProgressItemEditHistory.id.notin_([e.id for e in window_entries]),
        )
    ).scalar_one()
    if remaining_edits == 0:
        item.is_manually_edited = False
        item.manual_edit_reason = None

    # 删掉被撤销的历史条目,使下次 undo 撤销的是 "更早一组"
    for entry in window_entries:
        db.delete(entry)

    db.commit()
    db.refresh(item)
    return item


def _resolve_progress_item_scope(
    db: Session,
    project_id: int,
    scope: str | None,
    batch_id: int | None,
    data_date: date | None,
    import_group_id: str | None,
    batch_ids: str | None,
) -> tuple[list[ImportBatch], ProgressItemScopeInfo]:
    normalized_scope = (scope or "").strip().lower()
    is_project_scope = normalized_scope == "project"
    batches: list[ImportBatch] = []
    message: str | None = None

    if is_project_scope:
        statement = select(ImportBatch).where(
            ImportBatch.project_id == project_id,
            ImportBatch.is_active.is_(True),
            ImportBatch.status == "published",
        )
        parsed_batch_ids = _parse_batch_ids(batch_ids)
        if import_group_id:
            statement = statement.where(ImportBatch.import_group_id == import_group_id)
        elif parsed_batch_ids:
            statement = statement.where(ImportBatch.id.in_(parsed_batch_ids))
        elif data_date is not None:
            statement = statement.where(ImportBatch.data_date == data_date)
        elif batch_id is not None:
            statement = statement.where(ImportBatch.id == batch_id)
        batches = list(db.scalars(statement.order_by(ImportBatch.data_date.asc().nullslast(), ImportBatch.id.asc())))
        message = "当前范围：项目级聚合明细。"
    else:
        batch = get_published_batch(db, project_id, batch_id)
        batches = [batch] if batch is not None else []
        message = "当前显示最新单批次明细。" if batch_id is None else "当前范围：单批次明细。"

    info = ProgressItemScopeInfo(
        scope="project" if is_project_scope else "batch",
        data_date=data_date or _single_data_date(batches),
        import_group_id=import_group_id or _single_import_group_id(batches),
        included_batch_ids=[batch.id for batch in batches],
        included_sheets=[batch.sheet_name or f"批次 {batch.id}" for batch in batches],
        task_count=0,
        message=message,
    )
    return batches, info


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


def _single_data_date(batches: list[ImportBatch]) -> date | None:
    values = {batch.data_date for batch in batches}
    return next(iter(values)) if len(values) == 1 else None


def _single_import_group_id(batches: list[ImportBatch]) -> str | None:
    values = {batch.import_group_id for batch in batches if batch.import_group_id}
    return next(iter(values)) if len(values) == 1 else None


def _status_filter_values(value: str) -> list[str]:
    if value == "delayed_or_worse":
        return ["seriously_delayed", "delayed"]
    if value == "any_delayed":
        return ["seriously_delayed", "delayed", "slightly_delayed"]
    return [value]


def _find_previous_item(db: Session, item: ProgressItem, batch: ImportBatch | None) -> ProgressItem | None:
    if batch is None or item.task_id is None:
        return None
    previous_batch_ids = (
        select(ImportBatch.id)
        .where(
            ImportBatch.project_id == item.project_id,
            ImportBatch.id != batch.id,
            ImportBatch.is_active.is_(True),
            ImportBatch.status.in_(["imported", "published"]),
        )
        .order_by(ImportBatch.data_date.desc().nullslast(), ImportBatch.id.desc())
    )
    return db.execute(
        select(ProgressItem)
        .where(ProgressItem.task_id == item.task_id, ProgressItem.batch_id.in_(previous_batch_ids))
        .order_by(ProgressItem.batch_id.desc())
    ).scalars().first()


def _progress_value_fields() -> set[str]:
    return EDITABLE_FIELDS.union(CALCULATED_FIELDS).union({"time_planned_percent", "imported_planned_percent", "schedule_phase", "current_period_quantity", "current_period_percent"})


def _prefer_recalculation_for_manual_edit(values: dict[str, Any], changed_fields: set[str]) -> None:
    quantity_actual_changed = changed_fields.intersection({"actual_quantity", "cumulative_quantity", "total_quantity"})
    quantity_plan_changed = changed_fields.intersection({"planned_quantity", "total_quantity"})
    if quantity_actual_changed and not changed_fields.intersection({"actual_percent", "reported_percent"}):
        values["actual_percent"] = None
        values["reported_percent"] = None
    if quantity_plan_changed and "planned_percent" not in changed_fields:
        values["planned_percent"] = None
    if quantity_actual_changed and "remaining_quantity" not in changed_fields:
        values["remaining_quantity"] = None


def _value_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime | date):
        return value.isoformat()
    return str(value)
