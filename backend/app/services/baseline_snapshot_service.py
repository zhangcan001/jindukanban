"""baseline_plan 版本快照服务。

负责：
1) 把当前基线下的 ProgressItem 的「计划部分」字段冻结成 JSON payload；
2) 列出某基线的所有快照；
3) 拿快照 payload 跟当前 ProgressItem 比对，输出"和这次快照相比，哪些任务的
   计划/实际/偏差变了"。

设计要点：
- 快照只存「计划维度」+ 关键标识 + 一份保留实际进度用于回顾，不复制 raw_data；
- 用 identity_key (兼容 task_code) 作为主对比键，缺失时回落到
  (task_name, building, floor, discipline)；
- 该模块完全不修改现有计算逻辑，只读 ProgressItem，写新表。
"""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.baseline_plan import BaselinePlan
from app.models.baseline_plan_snapshot import BaselinePlanSnapshot
from app.models.progress_item import ProgressItem

PLAN_FIELDS = (
    "planned_start_date",
    "planned_finish_date",
    "planned_quantity",
    "planned_percent",
    "imported_planned_percent",
    "time_planned_percent",
    "total_quantity",
    "weight",
)

ACTUAL_FIELDS = (
    "actual_start_date",
    "actual_finish_date",
    "actual_quantity",
    "actual_percent",
    "cumulative_quantity",
    "progress_deviation",
    "schedule_phase",
)


def _serialize_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _item_identity(item: ProgressItem) -> str:
    if item.identity_key:
        return item.identity_key
    parts = [
        item.task_code or "",
        item.task_name or "",
        item.building or "",
        item.floor or "",
        item.discipline or "",
    ]
    return "|".join(parts)


def _build_item_payload(item: ProgressItem) -> dict:
    record: dict = {
        "identity": _item_identity(item),
        "item_id": item.id,
        "task_id": item.task_id,
        "task_code": item.task_code,
        "task_name": item.task_name,
        "building": item.building,
        "floor": item.floor,
        "discipline": item.discipline,
        "construction_unit": item.construction_unit,
        "system_name": item.system_name,
        "unit": item.unit,
    }
    record["plan"] = {field: _serialize_value(getattr(item, field)) for field in PLAN_FIELDS}
    record["actual"] = {field: _serialize_value(getattr(item, field)) for field in ACTUAL_FIELDS}
    return record


def _gather_items(db: Session, baseline_plan_id: int) -> list[ProgressItem]:
    statement = (
        select(ProgressItem)
        .where(ProgressItem.baseline_plan_id == baseline_plan_id)
        .order_by(ProgressItem.id.asc())
    )
    return list(db.scalars(statement).all())


def create_snapshot(
    db: Session,
    baseline_plan: BaselinePlan,
    *,
    label: str,
    description: str | None = None,
    snapshot_date: date | None = None,
    created_by: str | None = None,
) -> BaselinePlanSnapshot:
    items = _gather_items(db, baseline_plan.id)
    payload = {
        "baseline_plan_id": baseline_plan.id,
        "baseline_plan_name": baseline_plan.name,
        "project_id": baseline_plan.project_id,
        "snapshot_date": (snapshot_date or date.today()).isoformat(),
        "items": [_build_item_payload(item) for item in items],
    }
    snapshot = BaselinePlanSnapshot(
        project_id=baseline_plan.project_id,
        baseline_plan_id=baseline_plan.id,
        snapshot_date=snapshot_date or date.today(),
        label=label,
        description=description,
        payload=json.dumps(payload, ensure_ascii=False),
        item_count=len(items),
        created_by=created_by,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def list_snapshots(db: Session, baseline_plan_id: int) -> list[BaselinePlanSnapshot]:
    statement = (
        select(BaselinePlanSnapshot)
        .where(BaselinePlanSnapshot.baseline_plan_id == baseline_plan_id)
        .order_by(BaselinePlanSnapshot.snapshot_date.desc().nullslast(), BaselinePlanSnapshot.id.desc())
    )
    return list(db.scalars(statement).all())


def _payload_items(snapshot: BaselinePlanSnapshot) -> list[dict]:
    try:
        data = json.loads(snapshot.payload)
    except (TypeError, ValueError):
        return []
    items = data.get("items") if isinstance(data, dict) else None
    return items if isinstance(items, list) else []


def _diff_field_set(snapshot_section: dict, current_section: dict, fields: Iterable[str]) -> dict:
    changes: dict = {}
    for field in fields:
        old_value = snapshot_section.get(field) if isinstance(snapshot_section, dict) else None
        new_value = current_section.get(field) if isinstance(current_section, dict) else None
        if old_value != new_value:
            changes[field] = {"before": old_value, "after": new_value}
    return changes


def compute_snapshot_diff(db: Session, snapshot: BaselinePlanSnapshot) -> dict:
    snapshot_items = _payload_items(snapshot)
    snapshot_by_identity = {entry.get("identity") or "": entry for entry in snapshot_items}

    current_items = _gather_items(db, snapshot.baseline_plan_id)
    current_payloads = [_build_item_payload(item) for item in current_items]
    current_by_identity = {entry["identity"]: entry for entry in current_payloads}

    added: list[dict] = []
    removed: list[dict] = []
    changed: list[dict] = []

    for identity, current_entry in current_by_identity.items():
        prior = snapshot_by_identity.get(identity)
        if prior is None:
            added.append({"identity": identity, "task_name": current_entry.get("task_name"), "after": current_entry})
            continue
        plan_changes = _diff_field_set(prior.get("plan", {}), current_entry["plan"], PLAN_FIELDS)
        actual_changes = _diff_field_set(prior.get("actual", {}), current_entry["actual"], ACTUAL_FIELDS)
        if plan_changes or actual_changes:
            changed.append(
                {
                    "identity": identity,
                    "task_name": current_entry.get("task_name"),
                    "building": current_entry.get("building"),
                    "floor": current_entry.get("floor"),
                    "discipline": current_entry.get("discipline"),
                    "plan_changes": plan_changes,
                    "actual_changes": actual_changes,
                }
            )

    for identity, prior in snapshot_by_identity.items():
        if identity not in current_by_identity:
            removed.append({"identity": identity, "task_name": prior.get("task_name"), "before": prior})

    return {
        "snapshot_id": snapshot.id,
        "snapshot_label": snapshot.label,
        "snapshot_date": snapshot.snapshot_date.isoformat() if snapshot.snapshot_date else None,
        "baseline_plan_id": snapshot.baseline_plan_id,
        "current_item_count": len(current_payloads),
        "snapshot_item_count": len(snapshot_items),
        "added_count": len(added),
        "removed_count": len(removed),
        "changed_count": len(changed),
        "added": added,
        "removed": removed,
        "changed": changed,
    }
