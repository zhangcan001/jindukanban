from datetime import date

from app.models.calculation_profile import CalculationProfile
from app.models.progress_item import ProgressItem
from app.services.progress_calculator import (
    DEFAULT_DELAY_THRESHOLDS,
    DelayThresholds,
    calculate_progress_fields,
    classify_delay_status,
    resolve_delay_thresholds,
)


def test_calculate_progress_fields_uses_quantity_and_previous_period() -> None:
    profile = CalculationProfile(
        project_id=1,
        name="按工程量优先",
        percent_source="quantity_first",
        enable_date_plan_calculation=True,
    )
    previous_item = ProgressItem(project_id=1, batch_id=1, actual_quantity=40, actual_percent=40)

    result = calculate_progress_fields(
        {
            "total_quantity": 100,
            "planned_quantity": 70,
            "cumulative_quantity": 55,
            "planned_start_date": date(2026, 5, 1),
            "planned_finish_date": date(2026, 5, 31),
        },
        profile,
        date(2026, 5, 16),
        previous_item,
    )

    assert result["actual_quantity"] == 55
    assert result["actual_percent"] == 55
    assert result["planned_percent"] == 50
    assert result["time_planned_percent"] == 50
    assert result["schedule_phase"] == "in_progress_by_plan"
    assert result["remaining_quantity"] == 45
    assert result["progress_deviation"] == 5
    assert result["status"] == "ahead"
    assert result["current_period_quantity"] == 15
    assert result["current_period_percent"] == 15


def test_calculate_progress_fields_uses_shared_percent_normalization() -> None:
    result = calculate_progress_fields(
        {
            "actual_percent": "0.58",
            "planned_percent": 0.5,
        },
        None,
        None,
    )

    assert result["actual_percent"] == 58
    assert result["planned_percent"] == 50
    assert result["imported_planned_percent"] == 50
    assert result["schedule_phase"] == "missing_plan_dates"


def test_calculate_progress_fields_accepts_textual_percent_status() -> None:
    not_started = calculate_progress_fields({"actual_percent": "未开始"}, None, None)
    completed = calculate_progress_fields({"actual_percent": "已完成"}, None, None)

    assert not_started["actual_percent"] == 0
    assert not_started["status"] == "missing_plan_dates"
    assert completed["actual_percent"] == 100
    assert completed["status"] == "missing_plan_dates"


def test_calculate_progress_fields_uses_quantity_fallback_for_actual_percent() -> None:
    result = calculate_progress_fields(
        {
            "total_quantity": 200,
            "cumulative_quantity": 80,
        },
        None,
        None,
    )

    assert result["actual_quantity"] == 80
    assert result["actual_percent"] == 40


def test_calculate_progress_fields_marks_future_plan_start_as_not_started_by_plan() -> None:
    result = calculate_progress_fields(
        {
            "actual_percent": 0,
            "planned_percent": 40,
            "planned_start_date": date(2026, 5, 20),
            "planned_finish_date": date(2026, 5, 30),
        },
        None,
        date(2026, 5, 18),
    )

    assert result["planned_percent"] == 0
    assert result["imported_planned_percent"] == 40
    assert result["progress_deviation"] == 0
    assert result["schedule_phase"] == "not_started_by_plan"
    assert result["status"] == "not_started_by_plan"


def test_calculate_progress_fields_uses_time_based_delay_after_plan_start() -> None:
    result = calculate_progress_fields(
        {
            "actual_percent": 0,
            "planned_percent": 40,
            "planned_start_date": date(2026, 5, 1),
            "planned_finish_date": date(2026, 5, 31),
        },
        None,
        date(2026, 5, 16),
    )

    assert result["planned_percent"] == 50
    assert result["progress_deviation"] == -50
    assert result["status"] == "seriously_delayed"


def test_calculate_progress_fields_marks_missing_dates_without_forcing_delay() -> None:
    result = calculate_progress_fields({"actual_percent": 0, "planned_percent": 40}, None, date(2026, 5, 18))

    assert result["planned_percent"] == 40
    assert result["imported_planned_percent"] == 40
    assert result["progress_deviation"] is None
    assert result["schedule_phase"] == "missing_plan_dates"
    assert result["status"] == "missing_plan_dates"


def test_calculate_progress_fields_marks_invalid_dates_without_forcing_delay() -> None:
    result = calculate_progress_fields(
        {
            "actual_percent": 0,
            "planned_percent": 80,
            "planned_start_date": date(2026, 5, 20),
            "planned_finish_date": date(2026, 5, 10),
        },
        None,
        date(2026, 5, 18),
    )

    assert result["planned_percent"] == 80
    assert result["time_planned_percent"] is None
    assert result["progress_deviation"] is None
    assert result["schedule_phase"] == "invalid_plan_dates"
    assert result["status"] == "invalid_plan_dates"


def test_calculate_progress_fields_plan_start_date_is_zero_percent() -> None:
    result = calculate_progress_fields(
        {
            "total_quantity": 100,
            "cumulative_quantity": 0,
            "planned_start_date": date(2026, 5, 1),
            "planned_finish_date": date(2026, 5, 31),
        },
        None,
        date(2026, 5, 1),
    )

    assert result["time_planned_percent"] == 0
    assert result["planned_percent"] == 0
    assert result["progress_deviation"] == 0
    assert result["status"] == "normal"


def test_classify_delay_status_boundaries_use_default_thresholds() -> None:
    assert classify_delay_status(None) == "unknown"
    assert classify_delay_status(5.0) == "ahead"  # 等于上界归入更高等级
    assert classify_delay_status(4.99) == "normal"
    assert classify_delay_status(-5.0) == "normal"
    assert classify_delay_status(-5.01) == "slightly_delayed"
    assert classify_delay_status(-10.0) == "slightly_delayed"
    assert classify_delay_status(-10.01) == "delayed"
    assert classify_delay_status(-20.0) == "delayed"
    assert classify_delay_status(-20.01) == "seriously_delayed"


def test_classify_delay_status_respects_custom_thresholds() -> None:
    """更严格的阈值（normal/minor/major 收紧）应让相同偏差落到更差的等级。"""

    strict = DelayThresholds(ahead=3.0, normal=-3.0, minor=-7.0, major=-15.0)
    # -8 在默认阈值下是 slightly_delayed，在严格阈值下是 delayed
    assert classify_delay_status(-8.0) == "slightly_delayed"
    assert classify_delay_status(-8.0, strict) == "delayed"


def test_resolve_delay_thresholds_returns_default_when_profile_none() -> None:
    assert resolve_delay_thresholds(None) == DEFAULT_DELAY_THRESHOLDS


def test_resolve_delay_thresholds_uses_profile_base_values() -> None:
    profile = CalculationProfile(
        project_id=1,
        name="自定义阈值",
        delay_threshold_ahead=8.0,
        delay_threshold_normal=-2.0,
        delay_threshold_minor=-8.0,
        delay_threshold_major=-18.0,
    )
    thresholds = resolve_delay_thresholds(profile)
    assert thresholds == DelayThresholds(ahead=8.0, normal=-2.0, minor=-8.0, major=-18.0)


def test_resolve_delay_thresholds_applies_dimension_override() -> None:
    """覆盖按 discipline > floor > building 顺序应用，缺失字段继承上一级。"""

    profile = CalculationProfile(
        project_id=1,
        name="按专业覆盖",
        delay_threshold_overrides='{"discipline": {"机电": {"normal": -3, "minor": -8, "major": -15}}}',
    )
    thresholds = resolve_delay_thresholds(profile, discipline="机电")
    assert thresholds.normal == -3.0
    assert thresholds.minor == -8.0
    assert thresholds.major == -15.0
    # ahead 没覆盖，应继承 profile 默认值
    assert thresholds.ahead == DEFAULT_DELAY_THRESHOLDS.ahead


def test_resolve_delay_thresholds_ignores_invalid_json() -> None:
    profile = CalculationProfile(
        project_id=1,
        name="坏 JSON",
        delay_threshold_overrides="{not valid json",
    )
    thresholds = resolve_delay_thresholds(profile, discipline="机电")
    # 不应抛错，回退到 profile 基础阈值（== 默认值，因为 profile 没显式设阈值）
    assert thresholds == DEFAULT_DELAY_THRESHOLDS


def test_calculate_progress_fields_honors_per_discipline_threshold() -> None:
    """profile 阈值覆盖应让 status 判定按专业分级——同样偏差不同专业出不同状态。"""

    profile = CalculationProfile(
        project_id=1,
        name="机电更严",
        enable_date_plan_calculation=True,
        # 机电收紧：normal 从 -5 收到 -2，minor 从 -10 收到 -5
        delay_threshold_overrides='{"discipline": {"机电": {"normal": -2, "minor": -5}}}',
    )
    # data_date = 2026-05-16，30 天计划过了 15 天 → time_planned = 50
    # 实际 47 → deviation = -3
    base = {
        "actual_percent": 47,
        "planned_start_date": date(2026, 5, 1),
        "planned_finish_date": date(2026, 5, 31),
    }
    no_discipline = calculate_progress_fields(dict(base), profile, date(2026, 5, 16))
    mep = calculate_progress_fields({**base, "discipline": "机电"}, profile, date(2026, 5, 16))

    assert no_discipline["progress_deviation"] == -3
    assert no_discipline["status"] == "normal"  # 默认 normal 阈值 -5：-3 >= -5
    assert mep["status"] == "slightly_delayed"  # 机电覆盖 normal=-2 → -3 < -2，但 -3 >= -5（覆盖后的 minor）
