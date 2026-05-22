from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
import json
import re
from statistics import mean
from typing import Any, Iterable, NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.baseline_plan import BaselinePlan
from app.models.calculation_profile import CalculationProfile
from app.models.import_batch import ImportBatch
from app.models.progress_item import ProgressItem
from app.models.project import Project
from app.services.progress_calculator import (
    DEFAULT_DELAY_THRESHOLDS,
    DelayThresholds,
    calculate_progress_fields,
    calculate_time_based_planned_percent,
)

DIMENSIONS = [
    "area",
    "construction_unit",
    "building",
    "floor",
    "discipline",
    "system_name",
    "unit",
    "status",
]

METRICS = [
    "actual_percent",
    "planned_percent",
    "time_planned_percent",
    "progress_deviation",
    "total_quantity",
    "actual_quantity",
    "planned_quantity",
    "remaining_quantity",
    "current_period_quantity",
    "current_period_percent",
    "value_amount",
    "weight",
]

AGGREGATIONS = ["avg", "sum", "min", "max", "count"]


class StatisticsContext(NamedTuple):
    algorithm: str
    label: str
    weight_source: str | None
    weight_count: int
    weight_total: float | None
    is_normalized: bool
    project_contribution_actual: float | None
    project_contribution_planned: float | None
    weight_warning: str | None
    reason: str | None
    method_description: str | None


CALCULATION_METHODS = {
    "auto": "自动推荐",
    "weighted_percent": "权重统计",
    "value_weighted_percent": "产值加权统计",
    "quantity_percent": "工程量统计",
    "percent_average": "进度百分比平均",
    "task_average": "任务平均统计",
}


def resolve_calculation_profile(
    db: Session,
    project_id: int,
    calculation_profile_id: int | None,
) -> CalculationProfile | None:
    if calculation_profile_id is not None:
        profile = db.get(CalculationProfile, calculation_profile_id)
        if profile is not None and profile.project_id == project_id:
            return profile

    project = db.get(Project, project_id)
    if project and project.default_calculation_profile_id:
        profile = db.get(CalculationProfile, project.default_calculation_profile_id)
        if profile is not None and profile.project_id == project_id:
            return profile

    return db.execute(
        select(CalculationProfile)
        .where(CalculationProfile.project_id == project_id)
        .order_by(CalculationProfile.is_default.desc(), CalculationProfile.id)
    ).scalars().first()


def get_published_batch(db: Session, project_id: int, batch_id: int | None) -> ImportBatch | None:
    statement = select(ImportBatch).where(
        ImportBatch.project_id == project_id,
        ImportBatch.is_active.is_(True),
        ImportBatch.status == "published",
    )
    if batch_id is not None:
        statement = statement.where(ImportBatch.id == batch_id)
    else:
        statement = statement.order_by(
            ImportBatch.data_date.is_(None),
            ImportBatch.data_date.desc(),
            ImportBatch.created_at.desc(),
            ImportBatch.id.desc(),
        )
    return db.execute(statement).scalars().first()


def list_published_batches(db: Session, project_id: int) -> list[ImportBatch]:
    return list(
        db.execute(
            select(ImportBatch)
            .where(
                ImportBatch.project_id == project_id,
                ImportBatch.is_active.is_(True),
                ImportBatch.status == "published",
            )
            .order_by(
                ImportBatch.data_date.is_(None),
                ImportBatch.data_date.asc(),
                ImportBatch.created_at.asc(),
                ImportBatch.id.asc(),
            )
        ).scalars()
    )


def list_items(db: Session, project_id: int, batch_id: int) -> list[ProgressItem]:
    return list(
        db.execute(
            select(ProgressItem)
            .where(ProgressItem.project_id == project_id, ProgressItem.batch_id == batch_id)
            .order_by(ProgressItem.id.asc())
        ).scalars()
    )


def apply_time_based_progress(
    items: list[ProgressItem],
    batch: ImportBatch,
    profile: CalculationProfile | None = None,
) -> list[ProgressItem]:
    """对 items 按 batch.data_date 重算 actual/planned/deviation/status 等字段。

    profile 非 None 时，calculation_profile 配置的滞后阈值会真正生效
    （历史实现固定传 None，导致 dashboard 重算路径忽略阈值配置）。
    """

    # 局部 import 避免循环：progress_engine 反向依赖 analytics_service 中的若干工具函数
    from app.services.progress_engine import ProgressEngine

    return ProgressEngine(profile=profile).apply(items, batch=batch)


def resolve_baseline_plan(db: Session, project_id: int, baseline_plan_id: int | None) -> BaselinePlan | None:
    if baseline_plan_id is None:
        return None
    baseline = db.get(BaselinePlan, baseline_plan_id)
    if baseline is not None and baseline.project_id == project_id and baseline.is_active:
        return baseline
    return None


def baseline_name(db: Session, project_id: int, baseline_plan_id: int | None) -> str | None:
    baseline = db.get(BaselinePlan, baseline_plan_id) if baseline_plan_id is not None else None
    if baseline is not None and baseline.project_id == project_id:
        return baseline.name
    return None


def effective_baseline_plan(
    db: Session,
    project_id: int,
    batch: ImportBatch,
    baseline_plan_id: int | None,
) -> BaselinePlan | None:
    requested = resolve_baseline_plan(db, project_id, baseline_plan_id)
    if requested is not None:
        return requested
    if baseline_plan_id is not None:
        return None
    return resolve_baseline_plan(db, project_id, batch.baseline_plan_id)


def baseline_context(db: Session, project_id: int, batch: ImportBatch, baseline_plan_id: int | None) -> dict[str, object]:
    current = effective_baseline_plan(db, project_id, batch, baseline_plan_id)
    bound_name = baseline_name(db, project_id, batch.baseline_plan_id)
    current_id = current.id if current else None
    current_name = current.name if current else None
    consistent = batch.baseline_plan_id == current_id
    if batch.baseline_plan_id is None and current_id is None:
        notice = "当前批次未绑定计划基线，系统仍可显示实际进度，但进度偏差和滞后判断仅基于导入表内计划字段。"
    elif not consistent:
        notice = "当前查看基线与批次绑定基线不同，请注意分析口径。"
    else:
        notice = f"当前批次采用计划基线：{current_name}。" if current_name else None
    return {
        "batch_bound_baseline_plan_id": batch.baseline_plan_id,
        "batch_bound_baseline_plan_name": bound_name,
        "current_view_baseline_plan_id": current_id,
        "current_view_baseline_plan_name": current_name,
        "baseline_consistent": consistent,
        "baseline_notice": notice,
    }


def filter_items_by_baseline(items: list[ProgressItem], baseline_plan: BaselinePlan | None) -> list[ProgressItem]:
    if baseline_plan is None:
        return items
    if items and not any(item.baseline_plan_id is not None for item in items):
        return items
    return [item for item in items if item.baseline_plan_id == baseline_plan.id]


def item_units(items: list[ProgressItem]) -> list[str]:
    return sorted({item.unit for item in items if item.unit})


def aggregate_progress(
    items: list[ProgressItem],
    profile: CalculationProfile | None,
    percent_field: str = "actual_percent",
    algorithm: str | None = None,
) -> tuple[float | None, bool, str | None]:
    algorithm = effective_algorithm(items, profile, algorithm)
    unit_mixed = has_mixed_units(items)
    if algorithm == "percent_average":
        return average([getattr(item, percent_field, None) for item in items]), unit_mixed, mixed_unit_warning(unit_mixed, profile)

    if algorithm == "task_average":
        return task_average_progress(items, percent_field), unit_mixed, mixed_unit_warning(unit_mixed, profile)

    if algorithm == "quantity_percent" and unit_mixed and not (profile and profile.allow_mixed_unit_sum):
        warning = "单位混杂，已改用平均完成率，未直接汇总工程量。"
        return average([getattr(item, percent_field, None) for item in items]), True, warning

    if algorithm == "quantity_percent":
        if percent_field == "actual_percent":
            return percent_from_sums(items, "cumulative_quantity", "total_quantity"), unit_mixed, mixed_unit_warning(unit_mixed, profile)
        return weighted_average(items, percent_field, "total_quantity"), unit_mixed, mixed_unit_warning(unit_mixed, profile)

    if algorithm in {"weighted_percent", "weighted_percent_normalized"} or (profile and profile.use_weight):
        return weighted_normalized_average(items, percent_field), unit_mixed, mixed_unit_warning(unit_mixed, profile)

    if algorithm == "value_weighted_percent" or (profile and profile.use_value_amount):
        return weighted_average(items, percent_field, "value_amount"), unit_mixed, mixed_unit_warning(unit_mixed, profile)

    if algorithm == "reported_percent" and percent_field == "actual_percent":
        return average([item.reported_percent for item in items]), unit_mixed, mixed_unit_warning(unit_mixed, profile)

    return average([getattr(item, percent_field, None) for item in items]), unit_mixed, mixed_unit_warning(unit_mixed, profile)


def effective_algorithm(
    items: list[ProgressItem],
    profile: CalculationProfile | None,
    algorithm: str | None = None,
) -> str:
    requested = normalize_algorithm_code(algorithm or ((profile.overall_algorithm if profile else "auto") or "auto"))
    if requested == "auto":
        recommended = recommended_calculation_method(items)
        return recommended or "task_average"
    if algorithm is None and requested in {"avg_percent", "percent_average"} and has_valid_weights(items):
        return "weighted_percent"
    return requested


def normalize_algorithm_code(value: str | None) -> str:
    aliases = {
        "avg_percent": "percent_average",
        "weighted_percent_normalized": "weighted_percent",
        "": "auto",
    }
    return aliases.get(value or "auto", value or "auto")


def effective_calculation_method(project: Project | None, calculation_method: str | None) -> str | None:
    requested = normalize_algorithm_code(calculation_method)
    if requested != "auto":
        return requested
    default_method = normalize_algorithm_code(project.default_calculation_method if project else None)
    return None if default_method == "auto" else default_method


def statistics_context(
    items: list[ProgressItem],
    profile: CalculationProfile | None,
    algorithm: str | None = None,
) -> StatisticsContext:
    methods = available_calculation_methods(items)
    recommended = next((method for method in methods if method["recommended"]), None)
    effective = effective_algorithm(items, profile, algorithm)
    if algorithm is None and recommended is not None:
        effective = str(recommended["code"])
    weights = [item.weight for item in items if item.weight is not None and item.weight > 0]
    labels = {
        **CALCULATION_METHODS,
        "reported_percent": "Excel 上报完成率",
    }
    method = next((item for item in methods if item["code"] == effective), None)
    return StatisticsContext(
        algorithm=effective,
        label=labels.get(effective, "默认统计口径"),
        weight_source=weight_source_from_items(items) if effective == "weighted_percent" and weights else None,
        weight_count=len(weights),
        weight_total=round(sum(weights), 6) if weights else None,
        is_normalized=effective in {"weighted_percent", "weighted_percent_normalized"} and bool(weights),
        project_contribution_actual=project_contribution(items, "actual_percent") if weights else None,
        project_contribution_planned=project_contribution(items, "planned_percent") if weights else None,
        weight_warning=weight_warning(items),
        reason=str(method.get("reason")) if method else None,
        method_description=calculation_method_description(effective),
    )


def available_calculation_methods(items: list[ProgressItem]) -> list[dict[str, object]]:
    has_weight = has_valid_weights(items)
    has_value = any(item.value_amount is not None and item.value_amount > 0 for item in items)
    has_quantity = any(item.total_quantity is not None and item.total_quantity > 0 and item.cumulative_quantity is not None for item in items)
    has_percent = any(item.actual_percent is not None for item in items)
    unit_mixed = has_mixed_units(items)
    recommended_code = recommended_calculation_method(items)

    rows = [
        {
            "code": "weighted_percent",
            "name": CALCULATION_METHODS["weighted_percent"],
            "available": has_weight,
            "reason": "检测到 Excel 中存在权重字段" if has_weight else "未检测到有效权重字段",
        },
        {
            "code": "value_weighted_percent",
            "name": CALCULATION_METHODS["value_weighted_percent"],
            "available": has_value,
            "reason": "检测到产值或金额字段" if has_value else "未检测到有效产值字段",
        },
        {
            "code": "quantity_percent",
            "name": CALCULATION_METHODS["quantity_percent"],
            "available": has_quantity,
            "reason": "检测到总工程量和累计完成量" if has_quantity else "未检测到完整工程量字段",
            "warning": "当前数据包含多种单位，直接汇总工程量可能失真" if has_quantity and unit_mixed else None,
        },
        {
            "code": "percent_average",
            "name": CALCULATION_METHODS["percent_average"],
            "available": has_percent,
            "reason": "检测到实际完成率字段" if has_percent else "未检测到实际完成率字段",
        },
        {
            "code": "task_average",
            "name": CALCULATION_METHODS["task_average"],
            "available": True,
            "reason": "缺少权重、产值、工程量或百分比字段时使用任务平均统计",
        },
    ]
    for row in rows:
        row["recommended"] = row["code"] == recommended_code
    return rows


def recommended_calculation_method(items: list[ProgressItem]) -> str:
    has_weight = has_valid_weights(items)
    has_value = any(item.value_amount is not None and item.value_amount > 0 for item in items)
    has_quantity = any(item.total_quantity is not None and item.total_quantity > 0 and item.cumulative_quantity is not None for item in items)
    has_percent = any(item.actual_percent is not None for item in items)
    unit_mixed = has_mixed_units(items)
    if has_weight:
        return "weighted_percent"
    if has_value:
        return "value_weighted_percent"
    if has_quantity and not unit_mixed:
        return "quantity_percent"
    if has_percent:
        return "percent_average"
    return "task_average"


def calculation_method_description(code: str) -> str:
    descriptions = {
        "weighted_percent": "按 Excel 权重字段加权，并按当前查看范围权重合计归一化。",
        "value_weighted_percent": "按产值或金额字段加权，并按当前查看范围产值合计归一化。",
        "quantity_percent": "实际进度按累计完成量/总工程量计算，应完成进度按时间计划和总工程量加权。",
        "percent_average": "对当前范围内任务实际完成率和应完成率取平均。",
        "task_average": "按已完成任务数/总任务数估算当前范围进度。",
    }
    return descriptions.get(code, "按当前统计口径计算。")


def has_valid_weights(items: list[ProgressItem]) -> bool:
    return any(item.weight is not None and item.weight > 0 for item in items)


def weight_warning(items: list[ProgressItem]) -> str | None:
    if not items:
        return None
    missing = sum(1 for item in items if item.weight is None)
    negative = sum(1 for item in items if item.weight is not None and item.weight < 0)
    over_one = sum(1 for item in items if item.weight is not None and item.weight > 1)
    total = sum(item.weight for item in items if item.weight is not None and item.weight > 0)
    messages = []
    if missing:
        messages.append(f"{missing} 项权重为空")
    if negative:
        messages.append(f"{negative} 项权重小于 0")
    if over_one:
        messages.append(f"{over_one} 项权重大于 1")
    if total == 0:
        messages.append("当前范围权重合计为 0")
    elif total < 0.98 or total > 1.02:
        messages.append(f"当前范围权重合计为 {total:.4f}，未接近 100%，已按当前范围权重合计归一化")
    return "；".join(messages) if messages else None


def weight_source_from_items(items: list[ProgressItem]) -> str:
    names: set[str] = set()
    for item in items:
        if item.weight is None or not item.extra_fields:
            continue
        try:
            extra = json.loads(item.extra_fields)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(extra, dict):
            continue
        names.update(str(key) for key in extra if "权重" in str(key))
    if names:
        return "Excel 字段：" + "、".join(sorted(names))
    return "Excel 权重字段"


def aggregate_metric(
    items: list[ProgressItem],
    metric: str,
    aggregation: str,
    profile: CalculationProfile | None,
    algorithm: str | None = None,
) -> tuple[float | int | None, bool, str | None]:
    if aggregation == "count":
        return len(items), has_mixed_units(items), mixed_unit_warning(has_mixed_units(items), profile)

    if metric in {"actual_percent", "planned_percent"} and aggregation == "avg":
        return aggregate_progress(items, profile, metric, algorithm)

    values = [getattr(item, metric) for item in items if getattr(item, metric) is not None]
    unit_mixed = has_mixed_units(items)
    if not values:
        return None, unit_mixed, mixed_unit_warning(unit_mixed, profile)
    if aggregation == "sum":
        if metric.endswith("_quantity") and unit_mixed and not (profile and profile.allow_mixed_unit_sum):
            return None, True, "单位混杂，未汇总数量字段。"
        return round(sum(values), 4), unit_mixed, mixed_unit_warning(unit_mixed, profile)
    if aggregation == "min":
        return round(min(values), 4), unit_mixed, mixed_unit_warning(unit_mixed, profile)
    if aggregation == "max":
        return round(max(values), 4), unit_mixed, mixed_unit_warning(unit_mixed, profile)
    return round(mean(values), 4), unit_mixed, mixed_unit_warning(unit_mixed, profile)


def group_items(items: Iterable[ProgressItem], dimension: str) -> dict[str | None, list[ProgressItem]]:
    groups: dict[str | None, list[ProgressItem]] = defaultdict(list)
    for item in items:
        empty_label = "未填写楼层" if dimension == "floor" else "未填写"
        groups[getattr(item, dimension) or empty_label].append(item)
    return groups


def group_items_multi(
    items: Iterable[ProgressItem], dimensions: list[str]
) -> dict[tuple[str, ...], list[ProgressItem]]:
    """按 1~N 个维度组合分组,用于偏差归因下钻。"""
    if not dimensions:
        return {(): list(items)}
    groups: dict[tuple[str, ...], list[ProgressItem]] = defaultdict(list)
    for item in items:
        key_parts: list[str] = []
        for dimension in dimensions:
            empty_label = "未填写楼层" if dimension == "floor" else "未填写"
            value = getattr(item, dimension, None) or empty_label
            key_parts.append(str(value))
        groups[tuple(key_parts)].append(item)
    return groups


def sort_dimension_value(dimension: str, value: str | None) -> tuple[int, int, str]:
    text = value or ""
    if dimension == "building":
        return sort_building_value(text)
    if dimension != "floor":
        return natural_text_key(text)
    return sort_floor_value(text)


def sort_building_value(text: str) -> tuple[int, int, str]:
    if text == "未填写楼栋":
        return (8, 0, text)
    fixed_order = {
        "地下室": (0, 0),
        "裙楼": (1, 0),
        "能源中心": (5, 0),
        "室外": (6, 0),
    }
    if text in fixed_order:
        major, minor = fixed_order[text]
        return (major, minor, text)
    match = re.search(r"(\d+)\s*号楼", text)
    if match:
        return (2, int(match.group(1)), text)
    return (7, 0, text)


def sort_floor_value(text: str) -> tuple[int, int, str]:
    if text == "未填写楼层":
        return (6, 0, text)
    underground = re_search_floor(text, ("地下", "B", "b", "负"))
    if underground is not None:
        return (0, underground, text)
    aboveground = re_search_floor(text, ("",))
    if aboveground is not None:
        return (1, aboveground, text)
    fixed_order = {
        "屋面": (2, 0),
        "管廊": (3, 0),
        "室外": (4, 0),
    }
    if text in fixed_order:
        major, minor = fixed_order[text]
        return (major, minor, text)
    return (5, 0, text)


def natural_text_key(text: str) -> tuple[int, int, str]:
    match = re.search(r"(\d+)", text)
    if match:
        return (0, int(match.group(1)), text)
    return (0, 0, text)


def re_search_floor(text: str, prefixes: tuple[str, ...]) -> int | None:
    for prefix in prefixes:
        if prefix:
            match = re.search(rf"{re.escape(prefix)}\s*(\d+)", text)
        else:
            match = re.search(r"^(\d+)\s*层?$", text)
        if match:
            value = int(match.group(1))
            return -value if prefix else value
    return None


def status_counts(items: list[ProgressItem]) -> dict[str, int]:
    return dict(Counter(item.status or "unknown" for item in items))


def delay_reference_date(batch: ImportBatch) -> date:
    return batch.data_date or date.today()


def is_not_started_by_plan(item: ProgressItem, reference_date: date) -> bool:
    return schedule_phase_for_item(item, reference_date) == "not_started_by_plan"


def schedule_phase_for_item(item: ProgressItem, reference_date: date) -> str:
    return calculate_time_based_planned_percent(item.planned_start_date, item.planned_finish_date, reference_date).schedule_phase


def is_delay_eligible(item: ProgressItem, reference_date: date) -> bool:
    return schedule_phase_for_item(item, reference_date) in {"in_progress_by_plan", "finished_by_plan"}


def calculated_deviation(item: ProgressItem, reference_date: date | None = None) -> float | None:
    if item.actual_percent is None or item.planned_percent is None:
        return None
    phase = item.schedule_phase or (schedule_phase_for_item(item, reference_date) if reference_date else None)
    if phase not in {None, "in_progress_by_plan", "finished_by_plan"}:
        return None
    return round(min(100, item.actual_percent) - item.planned_percent, 4)


def delayed_items(items: list[ProgressItem], reference_date: date) -> list[ProgressItem]:
    delayed = [
        item
        for item in items
        if is_delay_eligible(item, reference_date)
        and calculated_deviation(item, reference_date) is not None
        and (calculated_deviation(item, reference_date) or 0) < 0
    ]
    delayed.sort(key=lambda item: calculated_deviation(item, reference_date) or 0)
    return delayed


def delayed_count(items: list[ProgressItem], reference_date: date) -> int:
    return len(delayed_items(items, reference_date))


def display_text(value: str | None, fallback: str) -> str:
    text = (value or "").strip()
    return text or fallback


def delay_level_for_deviation(
    deviation: float | None,
    thresholds: DelayThresholds = DEFAULT_DELAY_THRESHOLDS,
) -> tuple[str, str]:
    """对已被认定为滞后的项进行严重程度分级。

    返回 (status_code, 中文标签)。仅产出 seriously_delayed/delayed/slightly_delayed/unknown，
    不返回 normal/ahead——调用方应在判定项目"已滞后"后再调本函数。
    阈值来源：progress_calculator.DelayThresholds，可由 calculation_profile 覆盖。
    """

    if deviation is None:
        return "unknown", "未知"
    if deviation < thresholds.major:
        return "seriously_delayed", "严重滞后"
    if deviation < thresholds.minor:
        return "delayed", "明显滞后"
    return "slightly_delayed", "轻微滞后"


def delay_percent_text(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{float(value):.1f}"


def build_delay_message(item: ProgressItem) -> str:
    discipline = display_text(item.discipline, "未填写专业")
    task_name = display_text(item.task_name, "未填写施工项")
    building = (item.building or "").strip()
    floor = (item.floor or "").strip()
    if building and floor:
        subject = f"{building} {floor} {task_name}"
    elif building:
        subject = f"{building} {task_name}"
    else:
        subject = task_name

    actual = delay_percent_text(item.actual_percent)
    planned = delay_percent_text(item.time_planned_percent if item.time_planned_percent is not None else item.planned_percent)
    deviation = delay_percent_text(abs(item.progress_deviation or 0))
    return f"【{discipline}】{subject}：按计划日期应完成 {planned}%，实际完成 {actual}%，滞后 {deviation} 个百分点。"


def has_mixed_units(items: list[ProgressItem]) -> bool:
    units = {item.unit for item in items if item.unit}
    return len(units) > 1


def mixed_unit_warning(unit_mixed: bool, profile: CalculationProfile | None) -> str | None:
    if unit_mixed and not (profile and profile.allow_mixed_unit_sum):
        return "单位混杂，数量类指标不建议直接求和。"
    return None


def average(values: Iterable[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return round(mean(clean), 4)


def weighted_average(items: list[ProgressItem], percent_field: str, weight_field: str) -> float | None:
    numerator = 0.0
    denominator = 0.0
    for item in items:
        percent = getattr(item, percent_field)
        weight = getattr(item, weight_field)
        if percent is None or weight is None:
            continue
        numerator += percent * weight
        denominator += weight
    if denominator == 0:
        return average([getattr(item, percent_field) for item in items])
    return round(numerator / denominator, 4)


def weighted_normalized_average(items: list[ProgressItem], percent_field: str) -> float | None:
    return weighted_average(items, percent_field, "weight")


def project_contribution(items: list[ProgressItem], percent_field: str) -> float | None:
    numerator = 0.0
    has_value = False
    for item in items:
        percent = getattr(item, percent_field)
        weight = item.weight
        if percent is None or weight is None or weight <= 0:
            continue
        numerator += percent * weight
        has_value = True
    return round(numerator, 4) if has_value else None


def task_average_progress(items: list[ProgressItem], percent_field: str) -> float | None:
    if percent_field != "actual_percent":
        return average([getattr(item, percent_field, None) for item in items])
    if not items:
        return None
    has_completion_signal = any(item.actual_percent is not None or item.status in {"completed", "done", "finished"} for item in items)
    if not has_completion_signal:
        return None
    completed = sum(1 for item in items if (item.actual_percent is not None and item.actual_percent >= 100) or item.status == "completed")
    return round(completed / len(items) * 100, 4)


def percent_from_sums(items: list[ProgressItem], numerator_field: str, denominator_field: str) -> float | None:
    numerator = sum(getattr(item, numerator_field) for item in items if getattr(item, numerator_field) is not None)
    denominator = sum(getattr(item, denominator_field) for item in items if getattr(item, denominator_field) is not None)
    if denominator == 0:
        return None
    return round(numerator / denominator * 100, 4)


def validate_dimension(dimension: str) -> None:
    if dimension not in DIMENSIONS:
        raise ValueError(f"Unsupported dimension: {dimension}")


def validate_metric(metric: str) -> None:
    if metric not in METRICS:
        raise ValueError(f"Unsupported metric: {metric}")


def validate_aggregation(aggregation: str) -> None:
    if aggregation not in AGGREGATIONS:
        raise ValueError(f"Unsupported aggregation: {aggregation}")


def quantity_sum(items: list[ProgressItem], field: str, profile: CalculationProfile | None) -> tuple[float | None, bool, str | None]:
    unit_mixed = has_mixed_units(items)
    if unit_mixed and not (profile and profile.allow_mixed_unit_sum):
        return None, True, "单位混杂，未汇总数量字段。"
    values = [getattr(item, field) for item in items if getattr(item, field) is not None]
    return (round(sum(values), 4) if values else None), unit_mixed, mixed_unit_warning(unit_mixed, profile)
