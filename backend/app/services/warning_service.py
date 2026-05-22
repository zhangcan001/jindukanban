from __future__ import annotations

from datetime import date

from sqlalchemy import delete, not_, or_, select
from sqlalchemy.orm import Session

from app.models.import_batch import ImportBatch
from app.models.progress_item import ProgressItem
from app.models.warning_record import WarningRecord
from app.models.warning_rule import WarningRule
from app.services.analytics_service import (
    apply_time_based_progress,
    calculated_deviation,
    is_delay_eligible,
    resolve_calculation_profile,
)

DATA_QUALITY_WARNING_RULE_TYPE = "low_data_quality"
DATA_QUALITY_WARNING_TITLE = "数据质量评分偏低"
DATA_QUALITY_WARNING_KEYWORD = "数据质量评分"

BUILTIN_RULES = [
    ("连续两期滞后", "consecutive_delayed", "warning", 2),
    ("严重滞后超过 10%", "serious_delay", "critical", 10),
    ("实际完成率连续两期无增长", "no_growth", "warning", 2),
    ("本期完成量为 0", "zero_period_quantity", "warning", 0),
    ("计划完成日期临近但完成率低于 80%", "near_finish_low_progress", "warning", 80),
]


def ensure_builtin_warning_rules(db: Session, project_id: int) -> list[WarningRule]:
    existing = {
        rule.rule_type: rule
        for rule in db.execute(select(WarningRule).where(WarningRule.project_id == project_id)).scalars()
    }
    for name, rule_type, level, threshold in BUILTIN_RULES:
        if rule_type not in existing:
            rule = WarningRule(
                project_id=project_id,
                name=name,
                rule_type=rule_type,
                level=level,
                threshold_value=threshold,
                is_enabled=True,
            )
            db.add(rule)
            existing[rule_type] = rule
    db.flush()
    return list(existing.values())


def run_warning_rules(db: Session, project_id: int, batch: ImportBatch) -> list[WarningRecord]:
    rules = [rule for rule in ensure_builtin_warning_rules(db, project_id) if rule.is_enabled]
    profile = resolve_calculation_profile(db, project_id, batch.calculation_profile_id)
    items = apply_time_based_progress(list(
        db.execute(
            select(ProgressItem)
            .where(ProgressItem.project_id == project_id, ProgressItem.batch_id == batch.id)
            .order_by(ProgressItem.id.asc())
        ).scalars()
    ), batch, profile)
    previous_items = _previous_items_by_task(db, project_id, batch)
    db.execute(
        delete(WarningRecord).where(
            WarningRecord.project_id == project_id,
            WarningRecord.batch_id == batch.id,
            not_(_legacy_data_quality_warning_filter()),
        )
    )

    records: list[WarningRecord] = []
    for rule in rules:
        if rule.rule_type == DATA_QUALITY_WARNING_RULE_TYPE:
            continue
        for item in items:
            previous = previous_items.get(item.task_id) if item.task_id is not None else None
            record = _check_item_rule(project_id, batch.id, item, previous, rule, batch.data_date)
            if record:
                records.append(record)

    db.add_all(records)
    db.flush()
    return records


def _previous_items_by_task(db: Session, project_id: int, batch: ImportBatch) -> dict[int, ProgressItem]:
    previous_batches = (
        select(ImportBatch.id)
        .where(
            ImportBatch.project_id == project_id,
            ImportBatch.id != batch.id,
            ImportBatch.status == "published",
            ImportBatch.is_active.is_(True),
        )
        .order_by(ImportBatch.data_date.desc().nullslast(), ImportBatch.published_at.desc().nullslast(), ImportBatch.id.desc())
    )
    result: dict[int, ProgressItem] = {}
    for item in db.execute(
        select(ProgressItem)
        .where(ProgressItem.project_id == project_id, ProgressItem.batch_id.in_(previous_batches), ProgressItem.task_id.is_not(None))
        .order_by(ProgressItem.batch_id.desc())
    ).scalars():
        if item.task_id is not None and item.task_id not in result:
            result[item.task_id] = item
    return result


def _check_item_rule(
    project_id: int,
    batch_id: int,
    item: ProgressItem,
    previous: ProgressItem | None,
    rule: WarningRule,
    data_date: date | None,
) -> WarningRecord | None:
    threshold = rule.threshold_value
    delay_eligible = is_delay_eligible(item, data_date or date.today())
    if not delay_eligible:
        return None
    if rule.rule_type == "consecutive_delayed":
        current_deviation = calculated_deviation(item, data_date)
        if previous and current_deviation is not None and current_deviation < 0 and (previous.progress_deviation or 0) < 0:
            return _record(project_id, batch_id, item, rule, f"{item.task_name} 连续两期滞后", f"当前偏差 {current_deviation}%，上一期偏差 {previous.progress_deviation}%。")
    if rule.rule_type == "serious_delay":
        limit = threshold if threshold is not None else 10
        current_deviation = calculated_deviation(item, data_date)
        if current_deviation is not None and current_deviation < -abs(limit):
            return _record(project_id, batch_id, item, rule, f"{item.task_name} 严重滞后", f"当前偏差 {current_deviation}%，超过 {abs(limit)}%。")
    if rule.rule_type == "no_growth":
        if _is_no_growth_warning_eligible(item, previous, data_date):
            return _record(project_id, batch_id, item, rule, f"{item.task_name} 实际完成率无增长", f"当前 {item.actual_percent}%，上一期 {previous.actual_percent}%。")
    if rule.rule_type == "zero_period_quantity":
        if item.current_period_quantity == 0 or item.period_quantity == 0:
            return _record(project_id, batch_id, item, rule, f"{item.task_name} 本期完成量为 0", "本期未产生有效完成量。")
    if rule.rule_type == "near_finish_low_progress":
        min_percent = threshold if threshold is not None else 80
        if data_date and item.planned_finish_date and 0 <= (item.planned_finish_date - data_date).days <= 7 and (item.actual_percent or 0) < min_percent:
            return _record(project_id, batch_id, item, rule, f"{item.task_name} 临近计划完成但完成率低", f"计划完成日期 {item.planned_finish_date}，实际完成率 {item.actual_percent or 0}%。")
    return None


def _is_no_growth_warning_eligible(item: ProgressItem, previous: ProgressItem | None, data_date: date | None) -> bool:
    if previous is None or item.actual_percent is None or previous.actual_percent is None:
        return False
    if item.actual_percent >= 100:
        return False
    if not is_delay_eligible(item, data_date or date.today()):
        return False

    current_deviation = calculated_deviation(item, data_date)
    if current_deviation is None or current_deviation >= 0:
        return False

    if item.time_planned_percent is None or item.actual_percent >= item.time_planned_percent:
        return False

    return item.actual_percent <= previous.actual_percent


def is_data_quality_warning_record(record: WarningRecord, rule: WarningRule | None = None) -> bool:
    if rule is not None and rule.rule_type == DATA_QUALITY_WARNING_RULE_TYPE:
        return True
    if record.task_id is not None:
        return False
    text = f"{record.title or ''} {record.message or ''}"
    return DATA_QUALITY_WARNING_TITLE in text or DATA_QUALITY_WARNING_KEYWORD in text


def _legacy_data_quality_warning_filter():
    return (
        WarningRecord.task_id.is_(None)
        & or_(
            WarningRecord.rule_id.in_(select(WarningRule.id).where(WarningRule.rule_type == DATA_QUALITY_WARNING_RULE_TYPE)),
            WarningRecord.title.contains(DATA_QUALITY_WARNING_TITLE),
            WarningRecord.message.contains(DATA_QUALITY_WARNING_KEYWORD),
        )
    )


def _record(project_id: int, batch_id: int, item: ProgressItem, rule: WarningRule, title: str, message: str) -> WarningRecord:
    warning_message = _item_warning_message(item, rule, message)
    return WarningRecord(
        project_id=project_id,
        batch_id=batch_id,
        task_id=item.task_id,
        rule_id=rule.id,
        level=rule.level,
        title=title,
        message=warning_message,
    )


def _item_warning_message(item: ProgressItem, rule: WarningRule, fallback_message: str) -> str:
    context = _item_context(item)
    actual = _format_percent(item.actual_percent)
    planned = _format_percent(item.planned_percent)
    rule_name = rule.name or "预警"

    if item.planned_percent is None:
        return f"{context}：当前实际完成 {actual}，缺少计划日期，无法判断应完成进度。"

    if item.progress_deviation is not None and item.progress_deviation < 0:
        return f"{context}：按计划日期应完成 {planned}，实际完成 {actual}，滞后 {_format_number(abs(item.progress_deviation))} 个百分点，触发{rule_name}。"

    if rule.rule_type == "zero_period_quantity":
        return f"{context}：实际完成 {actual}，应完成 {planned}，本期完成量为 0，触发{rule_name}。"

    if rule.rule_type == "no_growth":
        return f"{context}：实际完成 {actual}，应完成 {planned}，实际完成率连续未增长，触发{rule_name}。"

    return f"{context}：{fallback_message}"


def _item_context(item: ProgressItem) -> str:
    discipline = _clean(item.discipline) or "未填写专业"
    building = _clean(item.building) or "未填写楼栋"
    floor = _clean(item.floor) or "未填写楼层"
    task_name = _clean(item.task_name) or "未填写施工项"
    system_name = _clean(item.system_name)
    subject_parts = [building, floor]
    if system_name:
        subject_parts.append(system_name)
    subject_parts.append(task_name)
    return f"【{discipline}】{' '.join(subject_parts)}"


def _format_percent(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1f}%"


def _format_number(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1f}"


def _clean(value: str | None) -> str:
    return value.strip() if value and value.strip() else ""
