from __future__ import annotations

from collections import Counter
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.import_batch import ImportBatch
from app.models.import_validation_issue import ImportValidationIssue
from app.models.progress_item import ProgressItem
from app.schemas.analytics import AnalyticsInsightResponse
from app.services.analytics_service import (
    aggregate_progress,
    apply_time_based_progress,
    delayed_items,
    delay_reference_date,
    display_text,
    effective_baseline_plan,
    filter_items_by_baseline,
    get_published_batch,
    group_items,
    has_mixed_units,
    is_delay_eligible,
    list_items,
    resolve_calculation_profile,
    sort_dimension_value,
)


def generate_progress_insight(
    db: Session,
    project_id: int,
    batch_id: int | None = None,
    calculation_profile_id: int | None = None,
    baseline_plan_id: int | None = None,
    building: str | None = None,
) -> AnalyticsInsightResponse:
    batch = get_published_batch(db, project_id, batch_id)
    if batch is None:
        raise LookupError("Published import batch not found")
    profile = resolve_calculation_profile(db, project_id, calculation_profile_id or batch.calculation_profile_id)
    baseline = effective_baseline_plan(db, project_id, batch, baseline_plan_id)
    items = filter_items_by_baseline(apply_time_based_progress(list_items(db, project_id, batch.id), batch, profile), baseline)
    issue_counts = _issue_code_counts(db, batch.id)

    context = InsightContext(
        batch=batch,
        items=items,
        profile=profile,
        selected_building=building,
        issue_counts=issue_counts,
    )
    return AnalyticsInsightResponse(
        overview_summary=_overview_summary(context),
        discipline_summary=_discipline_summary(context),
        floor_summary=_floor_summary(context),
        building_floor_summary=_building_floor_summary(context),
        delay_summary=_delay_summary(context),
        quality_summary=_quality_summary(context),
        focus_points=_focus_points(context),
        recommended_actions=_recommended_actions(context),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


class InsightContext:
    def __init__(
        self,
        batch: ImportBatch,
        items: list[ProgressItem],
        profile,
        selected_building: str | None,
        issue_counts: Counter[str],
    ) -> None:
        self.batch = batch
        self.items = items
        self.profile = profile
        self.selected_building = selected_building
        self.issue_counts = issue_counts
        self.actual_percent, _, _ = aggregate_progress(items, profile, "actual_percent")
        self.planned_percent, _, _ = aggregate_progress(items, profile, "planned_percent")
        self.deviation = (
            round(self.actual_percent - self.planned_percent, 4)
            if self.actual_percent is not None and self.planned_percent is not None
            else None
        )
        task_ids = {item.task_id for item in items if item.task_id is not None}
        self.task_count = len(task_ids) if task_ids else len(items)
        self.reference_date = delay_reference_date(batch)
        self.not_started_by_plan_count = sum(1 for item in items if not is_delay_eligible(item, self.reference_date))


def _overview_summary(context: InsightContext) -> str:
    data_date = context.batch.data_date.isoformat() if context.batch.data_date else "当前数据日期"
    actual = context.actual_percent
    planned = context.planned_percent
    deviation = context.deviation
    if actual is None:
        return "当前批次缺少可计算的实际进度字段，建议检查字段映射是否包含实际完成率、实际完成量或累计完成量。"
    if planned is None:
        return (
            f"截至 {data_date}，本项目实际完成率为 {_number(actual)}%。"
            "当前批次缺少计划进度字段，暂无法准确判断相对于计划的滞后程度，建议后续补充计划完成率、计划完成量或计划基线数据。"
        )

    quality_score = _number(context.batch.data_quality_score) if context.batch.data_quality_score is not None else "-"
    summary = (
        f"截至 {data_date}，本项目实际完成率为 {_number(actual)}%，按计划日期应完成率为 {_number(planned)}%，"
        f"整体进度偏差为 {_number(deviation)} 个百分点。本期共纳入 {context.task_count} 项进度任务，"
        f"数据质量评分为 {quality_score} 分。"
    )
    if context.not_started_by_plan_count:
        summary += f"当前有 {context.not_started_by_plan_count} 项任务尚未到计划开始时间，未纳入滞后判断。"
    if deviation is not None and deviation <= -10:
        return summary + "整体进度明显滞后，需重点关注严重滞后的专业、楼栋、楼层及关键施工项，建议结合周例会落实整改措施。"
    if deviation is not None and deviation <= -5:
        return summary + "整体进度存在一定滞后，建议持续跟踪主要滞后项，重点核实施工资源、材料到场和交叉作业影响。"
    if deviation is not None and deviation < 0:
        return summary + "整体进度轻微滞后，当前总体可控，但仍需关注局部滞后任务，防止滞后扩大。"
    return summary + "整体进度总体可控，实际完成情况达到或优于计划要求，建议继续保持当前推进节奏。"


def _discipline_summary(context: InsightContext) -> str:
    if context.planned_percent is None:
        return "当前批次缺少计划进度字段，暂无法生成分专业滞后判断。"
    delayed = _group_deviations(context.items, context.profile, "discipline", require_source_field=False, reference_date=context.reference_date)[:3]
    if not delayed:
        return "当前分专业进度暂无明显滞后。"
    names = "、".join(name for _, name in delayed)
    details = "，".join(f"{name}专业进度偏差为 {_number(deviation)} 个百分点" for deviation, name in delayed[:2])
    if len(delayed) == 1:
        return f"从分专业情况看，当前滞后较明显的专业为{delayed[0][1]}。其中，{details}，建议作为本期协调重点。"
    return f"从分专业情况看，当前滞后较明显的专业主要包括：{names}。其中，{details}，建议作为本期协调重点。"


def _floor_summary(context: InsightContext) -> str:
    if not any((item.floor or "").strip() for item in context.items):
        return "当前批次暂无楼层统计数据，建议检查字段映射中是否包含楼层字段。"
    delayed = _group_deviations(context.items, context.profile, "floor", require_source_field=True, reference_date=context.reference_date)[:3]
    if not delayed:
        return "当前楼层进度暂无明显滞后。"
    floors = "、".join(name for _, name in delayed)
    return f"从楼层维度看，当前滞后较明显的楼层包括：{floors}。建议结合现场施工面、材料供应和专业穿插情况，重点跟踪上述楼层的施工推进。"


def _building_floor_summary(context: InsightContext) -> str:
    groups: dict[tuple[str, str], list[ProgressItem]] = {}
    for item in context.items:
        building = display_text(item.building, "未填写楼栋")
        floor = display_text(item.floor, "未填写楼层")
        if context.selected_building and building != context.selected_building:
            continue
        groups.setdefault((building, floor), []).append(item)
    if not groups:
        return "当前批次暂无楼栋楼层统计数据。"
    delayed: list[tuple[float, str, str]] = []
    for (building, floor), group in groups.items():
        actual, _, _ = aggregate_progress(group, context.profile, "actual_percent", _group_algorithm(context.profile))
        planned, _, _ = aggregate_progress(group, context.profile, "planned_percent", _group_algorithm(context.profile))
        if actual is None or planned is None:
            continue
        deviation = round(actual - planned, 4)
        if deviation < 0 and any(is_delay_eligible(item, context.reference_date) for item in group):
            delayed.append((deviation, building, floor))
    delayed.sort(key=lambda row: (row[0], sort_dimension_value("building", row[1]), sort_dimension_value("floor", row[2])))
    if not delayed:
        return "当前楼栋楼层维度暂无明显滞后。"
    names = "、".join(f"{building} {floor}" for _, building, floor in delayed[:5])
    return f"从楼栋楼层维度看，{names}进度偏差较大，建议作为现场巡查、工序协调和整改跟踪的重点区域。"


def _delay_summary(context: InsightContext) -> str:
    delayed = delayed_items(context.items, context.reference_date)[:5]
    if not delayed:
        return "当前批次暂无滞后项。"
    names = "、".join(_item_subject(item, include_discipline=True) for item in delayed[:5])
    first = delayed[0]
    return (
        f"主要滞后施工项包括：{names}等。"
        f"其中，{_item_subject(first, include_discipline=True)}滞后 {_number(abs(first.progress_deviation or 0))} 个百分点，建议优先跟踪。"
    )


def _quality_summary(context: InsightContext) -> str:
    score = context.batch.data_quality_score
    parts: list[str] = []
    if score is None:
        parts.append("当前批次暂未生成数据质量评分，建议结合校验提示复核关键字段。")
    elif score >= 85:
        parts.append("当前批次数据质量较好，可作为本期进度分析和汇报依据。")
    elif score >= 60:
        parts.append("当前批次数据质量一般，建议关注校验提示，并在正式汇报前复核关键字段和异常数据。")
    else:
        parts.append("当前批次数据质量偏低，建议重点检查字段映射、表头识别、日期格式、异常数据和缺失字段。")
    if context.batch.warning_count:
        parts.append(f"当前批次存在 {context.batch.warning_count} 条 warning，建议在正式汇报前进行复核。")
    if context.batch.error_count:
        parts.append(f"当前批次存在 {context.batch.error_count} 条 error，建议优先修正后再用于正式汇报。")
    if context.issue_counts.get("INVALID_DATE", 0) > 0:
        parts.append("存在日期格式异常，建议检查计划开始时间和计划完成时间。")
    if context.issue_counts.get("SUMMARY_ROW_SKIPPED", 0) > 0:
        parts.append("系统已自动跳过合计、汇总或小计行，避免重复统计。")
    if context.issue_counts.get("negative_quantity", 0) > 0:
        parts.append("存在工程量为负数的数据，建议复核原始 Excel。")
    if context.issue_counts.get("percent_out_of_range", 0) > 0:
        parts.append("存在完成率超出 0-100 范围的数据，建议核对实际完成情况。")
    return "".join(parts)


def _focus_points(context: InsightContext) -> list[str]:
    points: list[str] = []
    severe = [item for item in context.items if is_delay_eligible(item, context.reference_date) and item.progress_deviation is not None and item.progress_deviation <= -10]
    if severe:
        points.append("重点关注严重滞后施工项，优先协调资源、材料到场和交叉作业影响。")
    discipline_counts = Counter(display_text(item.discipline, "未填写专业") for item in severe)
    discipline, count = discipline_counts.most_common(1)[0] if discipline_counts else ("", 0)
    if count >= 2:
        points.append(f"重点关注{discipline}专业滞后项，建议安排专题协调。")
    floor_names = [name for _, name in _group_deviations(context.items, context.profile, "floor", require_source_field=True, reference_date=context.reference_date)[:2]]
    if floor_names:
        points.append(f"重点关注 {'、'.join(floor_names)} 等滞后楼层，核实施工条件和穿插作业影响。")
    if has_mixed_units(context.items):
        points.append("当前数据包含多种单位，数量类指标不宜直接求和，建议使用任务平均完成率、权重完成率或产值完成率。")
    if context.planned_percent is None:
        points.append("建议后续补充计划完成率、计划完成量或计划基线数据，以便准确判断进度偏差。")
    if context.batch.data_quality_score is not None and context.batch.data_quality_score < 60:
        points.append("建议先完善基础数据质量，再用于正式进度汇报。")
    if not points:
        points.append("本期整体进度暂无突出风险，建议保持常态化跟踪。")
    return _dedupe(points)[:5]


def _recommended_actions(context: InsightContext) -> list[str]:
    actions: list[str] = []
    if any(is_delay_eligible(item, context.reference_date) and item.progress_deviation is not None and item.progress_deviation <= -10 for item in context.items):
        actions.append("对严重滞后项建立整改清单，明确责任人、整改措施和计划完成时间。")
    if any(is_delay_eligible(item, context.reference_date) and item.progress_deviation is not None and -10 < item.progress_deviation <= -5 for item in context.items):
        actions.append("对明显滞后项持续跟踪，结合周例会检查整改进展。")
    if context.issue_counts.get("INVALID_DATE", 0) > 0:
        actions.append("复核计划开始时间和计划完成时间，避免无效日期影响计划分析。")
    if context.batch.data_quality_score is not None and context.batch.data_quality_score < 60:
        actions.append("完善字段映射和基础数据，优先保证施工项、楼栋、楼层、实际进度字段准确。")
    if has_mixed_units(context.items):
        actions.append("对单位混杂数据优先采用任务平均、权重或产值口径进行统计，避免直接汇总数量。")
    if context.planned_percent is None:
        actions.append("后续进度表建议补充计划完成率或计划完成量字段，以便生成准确的滞后分析。")
    if not actions:
        actions.append("保持现有跟踪频率，持续关注关键施工项和数据质量。")
    return _dedupe(actions)[:5]


def _group_deviations(
    items: list[ProgressItem],
    profile,
    dimension: str,
    require_source_field: bool,
    reference_date,
) -> list[tuple[float, str]]:
    candidates: list[tuple[float, str]] = []
    filtered_items = [item for item in items if (getattr(item, dimension) or "").strip()] if require_source_field else items
    for name, group in group_items(filtered_items, dimension).items():
        group = [item for item in group if is_delay_eligible(item, reference_date)]
        if not group:
            continue
        actual, _, _ = aggregate_progress(group, profile, "actual_percent", _group_algorithm(profile))
        planned, _, _ = aggregate_progress(group, profile, "planned_percent", _group_algorithm(profile))
        if actual is None or planned is None:
            continue
        deviation = round(actual - planned, 4)
        if deviation < 0:
            candidates.append((deviation, display_text(str(name) if name is not None else None, "未填写")))
    candidates.sort(key=lambda row: (row[0], sort_dimension_value(dimension, row[1])))
    return candidates


def _issue_code_counts(db: Session, batch_id: int) -> Counter[str]:
    counter: Counter[str] = Counter()
    for code, count in db.execute(
        select(ImportValidationIssue.code, func.count(ImportValidationIssue.id))
        .where(ImportValidationIssue.batch_id == batch_id)
        .group_by(ImportValidationIssue.code)
    ).all():
        counter[code or "UNKNOWN"] += int(count)
    return counter


def _item_subject(item: ProgressItem, include_discipline: bool = False) -> str:
    parts = [
        (item.building or "").strip(),
        (item.floor or "").strip(),
        display_text(item.task_name, "未填写施工项"),
    ]
    subject = " ".join(part for part in parts if part)
    if include_discipline and (item.discipline or "").strip():
        return f"【{item.discipline.strip()}】{subject}"
    return subject


def _group_algorithm(profile) -> str:
    return ((profile.group_algorithm if profile else "avg_percent") or "avg_percent")


def _number(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{float(value):.1f}"


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
