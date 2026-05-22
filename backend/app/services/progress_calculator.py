from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from typing import Any

from app.models.calculation_profile import CalculationProfile
from app.models.progress_item import ProgressItem
from app.utils.number_utils import normalize_percent


@dataclass(frozen=True)
class TimeBasedPlanResult:
    time_planned_percent: float | None
    schedule_phase: str


@dataclass(frozen=True)
class DelayThresholds:
    """偏差阈值（progress_deviation 单位为百分点）。

    判定顺序：deviation >= ahead → ahead，>= normal → normal，
    >= minor → slightly_delayed，>= major → delayed，否则 seriously_delayed。
    """

    ahead: float = 5.0
    normal: float = -5.0
    minor: float = -10.0
    major: float = -20.0


DEFAULT_DELAY_THRESHOLDS = DelayThresholds()


def classify_delay_status(
    deviation: float | None,
    thresholds: DelayThresholds = DEFAULT_DELAY_THRESHOLDS,
) -> str:
    """根据偏差与阈值返回标准状态码：
    ahead / normal / slightly_delayed / delayed / seriously_delayed / unknown。

    所有 dashboard / 报表服务都应通过此函数获取偏差等级，避免阈值各处硬编码。
    deviation=None 返回 unknown。
    """

    if deviation is None:
        return "unknown"
    if deviation >= thresholds.ahead:
        return "ahead"
    if deviation >= thresholds.normal:
        return "normal"
    if deviation >= thresholds.minor:
        return "slightly_delayed"
    if deviation >= thresholds.major:
        return "delayed"
    return "seriously_delayed"


def resolve_delay_thresholds(
    profile: CalculationProfile | None,
    *,
    discipline: str | None = None,
    floor: str | None = None,
    building: str | None = None,
) -> DelayThresholds:
    """根据 profile 解析阈值，并应用维度覆盖。

    覆盖优先级：discipline > floor > building > profile 基础值。
    任一覆盖键缺失则继承上一级。
    """

    if profile is None:
        return DEFAULT_DELAY_THRESHOLDS

    base = DelayThresholds(
        ahead=profile.delay_threshold_ahead if profile.delay_threshold_ahead is not None else DEFAULT_DELAY_THRESHOLDS.ahead,
        normal=profile.delay_threshold_normal if profile.delay_threshold_normal is not None else DEFAULT_DELAY_THRESHOLDS.normal,
        minor=profile.delay_threshold_minor if profile.delay_threshold_minor is not None else DEFAULT_DELAY_THRESHOLDS.minor,
        major=profile.delay_threshold_major if profile.delay_threshold_major is not None else DEFAULT_DELAY_THRESHOLDS.major,
    )

    overrides_raw = getattr(profile, "delay_threshold_overrides", None)
    if not overrides_raw:
        return base
    try:
        overrides = json.loads(overrides_raw)
    except (TypeError, json.JSONDecodeError):
        return base
    if not isinstance(overrides, dict):
        return base

    result = {"ahead": base.ahead, "normal": base.normal, "minor": base.minor, "major": base.major}
    for key, value in (("building", building), ("floor", floor), ("discipline", discipline)):
        bucket = overrides.get(key)
        if not isinstance(bucket, dict) or value is None:
            continue
        override = bucket.get(value)
        if not isinstance(override, dict):
            continue
        for threshold_key in ("ahead", "normal", "minor", "major"):
            if threshold_key in override and override[threshold_key] is not None:
                try:
                    result[threshold_key] = float(override[threshold_key])
                except (TypeError, ValueError):
                    continue
    return DelayThresholds(**result)


def calculate_progress_fields(
    values: dict[str, Any],
    calculation_profile: CalculationProfile | None,
    data_date: date | None,
    previous_item: ProgressItem | None = None,
) -> dict[str, Any]:
    result = values.copy()
    enable_date_plan = True if calculation_profile is None else calculation_profile.enable_date_plan_calculation
    percent_source = "quantity_first" if calculation_profile is None else calculation_profile.percent_source

    if result.get("actual_quantity") is None and result.get("cumulative_quantity") is not None:
        result["actual_quantity"] = result.get("cumulative_quantity")
    if "imported_planned_percent" not in result:
        result["imported_planned_percent"] = _normalize_percent(result.get("planned_percent"))

    plan_result = calculate_time_based_planned_percent(
        result.get("planned_start_date"),
        result.get("planned_finish_date"),
        data_date or date.today(),
    )
    time_planned_percent = plan_result.time_planned_percent if enable_date_plan else None
    result["schedule_phase"] = plan_result.schedule_phase if enable_date_plan else "missing_plan_dates"
    result["time_planned_percent"] = time_planned_percent

    result["actual_percent"] = _calculate_actual_percent(result, percent_source)
    result["planned_percent"] = _calculate_planned_percent(
        result,
        percent_source,
        time_planned_percent,
        enable_date_plan,
        plan_result.schedule_phase,
    )
    result["remaining_quantity"] = _calculate_remaining_quantity(result)

    actual_percent = result.get("actual_percent")
    planned_percent = result.get("planned_percent")
    result["progress_deviation"] = (
        round(_percent_for_status(actual_percent) - time_planned_percent, 4)
        if actual_percent is not None and time_planned_percent is not None
        else None
    )
    thresholds = resolve_delay_thresholds(
        calculation_profile,
        discipline=result.get("discipline"),
        floor=result.get("floor"),
        building=result.get("building"),
    )
    result["status"] = _calculate_status(
        result.get("actual_percent"),
        result.get("planned_percent"),
        result.get("progress_deviation"),
        result["schedule_phase"],
        thresholds,
    )

    current_period_quantity, current_period_percent = _calculate_current_period(result, previous_item)
    result["current_period_quantity"] = current_period_quantity
    result["current_period_percent"] = current_period_percent

    return result


def _calculate_actual_percent(values: dict[str, Any], percent_source: str) -> float | None:
    calculated = _percent_from_quantity(values.get("cumulative_quantity"), values.get("total_quantity"))
    if calculated is None:
        calculated = _percent_from_quantity(values.get("actual_quantity"), values.get("total_quantity"))
    if calculated is not None:
        return calculated

    if percent_source == "quantity_first":
        return _first_percent(values.get("actual_percent"), values.get("reported_percent"))

    provided = _first_percent(values.get("actual_percent"), values.get("reported_percent"))
    if provided is not None:
        return provided
    return None


def _calculate_planned_percent(
    values: dict[str, Any],
    percent_source: str,
    time_planned_percent: float | None,
    enable_date_plan: bool,
    schedule_phase: str,
) -> float | None:
    if enable_date_plan and time_planned_percent is not None:
        return time_planned_percent

    if percent_source == "quantity_first":
        calculated = _percent_from_quantity(values.get("planned_quantity"), values.get("total_quantity"))
        if calculated is not None:
            return calculated
        provided = _normalize_percent(values.get("planned_percent"))
        return provided if provided is not None else time_planned_percent

    provided = _normalize_percent(values.get("planned_percent"))
    if provided is not None:
        return provided
    calculated = _percent_from_quantity(values.get("planned_quantity"), values.get("total_quantity"))
    if calculated is not None:
        return calculated
    if schedule_phase in {"missing_plan_dates", "invalid_plan_dates"}:
        return _normalize_percent(values.get("planned_percent"))
    return time_planned_percent


def calculate_time_based_planned_percent(
    planned_start_date: date | None,
    planned_finish_date: date | None,
    data_date: date | None,
) -> TimeBasedPlanResult:
    if planned_start_date is None or planned_finish_date is None or data_date is None:
        return TimeBasedPlanResult(None, "missing_plan_dates")
    if planned_finish_date < planned_start_date:
        return TimeBasedPlanResult(None, "invalid_plan_dates")
    if data_date < planned_start_date:
        return TimeBasedPlanResult(0, "not_started_by_plan")
    if data_date >= planned_finish_date:
        return TimeBasedPlanResult(100, "finished_by_plan")
    total_days = (planned_finish_date - planned_start_date).days
    if total_days <= 0:
        return TimeBasedPlanResult(100, "finished_by_plan")
    elapsed_days = (data_date - planned_start_date).days
    percent = max(0, min(100, round(elapsed_days / total_days * 100, 1)))
    return TimeBasedPlanResult(percent, "in_progress_by_plan")


def _calculate_remaining_quantity(values: dict[str, Any]) -> float | None:
    remaining_quantity = values.get("remaining_quantity")
    if remaining_quantity is not None:
        return remaining_quantity
    total_quantity = values.get("total_quantity")
    actual_quantity = values.get("actual_quantity")
    cumulative_quantity = values.get("cumulative_quantity")
    if total_quantity is not None and actual_quantity is not None:
        return round(total_quantity - actual_quantity, 4)
    if total_quantity is not None and cumulative_quantity is not None:
        return round(total_quantity - cumulative_quantity, 4)
    return None


def _calculate_status(
    actual_percent: float | None,
    planned_percent: float | None,
    progress_deviation: float | None,
    schedule_phase: str,
    thresholds: DelayThresholds = DEFAULT_DELAY_THRESHOLDS,
) -> str:
    if schedule_phase == "not_started_by_plan":
        return "not_started_by_plan"
    if schedule_phase == "missing_plan_dates":
        return "missing_plan_dates"
    if schedule_phase == "invalid_plan_dates":
        return "invalid_plan_dates"
    if actual_percent is not None and actual_percent >= 100:
        return "completed"
    if planned_percent is None or progress_deviation is None:
        return "unknown"
    if progress_deviation >= thresholds.ahead:
        return "ahead"
    if progress_deviation >= thresholds.normal:
        return "normal"
    if progress_deviation >= thresholds.minor:
        return "slightly_delayed"
    if progress_deviation >= thresholds.major:
        return "delayed"
    return "seriously_delayed"


def _calculate_current_period(values: dict[str, Any], previous_item: ProgressItem | None) -> tuple[float | None, float | None]:
    period_quantity = values.get("period_quantity")
    total_quantity = values.get("total_quantity")
    if period_quantity is not None:
        return period_quantity, _percent_from_quantity(period_quantity, total_quantity)

    actual_quantity = values.get("actual_quantity")
    actual_percent = values.get("actual_percent")
    if previous_item is None:
        return None, None

    current_period_quantity = None
    if actual_quantity is not None and previous_item.actual_quantity is not None:
        current_period_quantity = round(actual_quantity - previous_item.actual_quantity, 4)

    current_period_percent = None
    if actual_percent is not None and previous_item.actual_percent is not None:
        current_period_percent = round(actual_percent - previous_item.actual_percent, 4)

    return current_period_quantity, current_period_percent


def _percent_from_quantity(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return round(numerator / denominator * 100, 4)


def _percent_for_status(value: float) -> float:
    return min(100, value)


def _first_percent(*values: Any) -> float | None:
    for value in values:
        percent = _normalize_percent(value)
        if percent is not None:
            return percent
    return None


def _normalize_percent(value: Any) -> float | None:
    return normalize_percent(value)
