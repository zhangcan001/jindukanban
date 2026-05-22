from datetime import date

from app.models.calculation_profile import CalculationProfile
from app.models.import_batch import ImportBatch
from app.models.progress_item import ProgressItem
from app.services.progress_engine import ProgressEngine


def _make_item(**overrides) -> ProgressItem:
    defaults = dict(
        project_id=1,
        batch_id=1,
        task_name="任务A",
        actual_percent=47,
        planned_start_date=date(2026, 5, 1),
        planned_finish_date=date(2026, 5, 31),
    )
    defaults.update(overrides)
    return ProgressItem(**defaults)


def test_apply_writes_calculated_fields_back_to_items() -> None:
    item = _make_item()
    batch = ImportBatch(
        project_id=1, file_name="x.xlsx", data_date=date(2026, 5, 16), status="published", is_active=True
    )
    engine = ProgressEngine()
    engine.apply([item], batch=batch)

    assert item.time_planned_percent == 50  # 30 天计划过 15 天
    assert item.progress_deviation == -3
    assert item.schedule_phase == "in_progress_by_plan"
    assert item.status == "normal"  # -3 >= -5 默认 normal 阈值


def test_engine_caches_compute_within_same_instance() -> None:
    item = _make_item()
    item.id = 42  # 模拟已持久化
    engine = ProgressEngine(default_data_date=date(2026, 5, 16))

    engine.compute(item)
    engine.compute(item)
    engine.compute(item)

    assert engine.stats.compute_count == 1
    assert engine.stats.cache_hit_count == 2


def test_engine_does_not_cache_when_previous_item_passed() -> None:
    """previous_item 影响 current_period_*，传 previous_item 时必须重算。"""

    item = _make_item(id=42)
    previous = _make_item(id=41, actual_percent=30)
    engine = ProgressEngine(default_data_date=date(2026, 5, 16))

    engine.compute(item)  # 缓存
    engine.compute(item, previous_item=previous)  # 重算
    engine.compute(item)  # 命中缓存

    assert engine.stats.compute_count == 2
    assert engine.stats.cache_hit_count == 1


def test_engine_passes_profile_thresholds_through() -> None:
    """ProgressEngine 把 calculation_profile 注入 calculate_progress_fields。"""

    strict = CalculationProfile(
        project_id=1,
        name="严格",
        enable_date_plan_calculation=True,
        delay_threshold_normal=-2.0,  # 收紧 normal：偏差 -3 不再属于 normal
    )
    item = _make_item()
    batch = ImportBatch(
        project_id=1, file_name="x.xlsx", data_date=date(2026, 5, 16), status="published", is_active=True
    )

    default_engine = ProgressEngine()
    default_engine.apply([item], batch=batch)
    assert item.status == "normal"  # -3 >= -5 默认 normal

    strict_engine = ProgressEngine(profile=strict)
    strict_engine.apply([item], batch=batch)
    assert item.status == "slightly_delayed"  # -3 < -2，但 >= -10


def test_invalidate_clears_cache() -> None:
    item = _make_item(id=42)
    engine = ProgressEngine(default_data_date=date(2026, 5, 16))
    engine.compute(item)
    engine.invalidate()
    engine.compute(item)
    assert engine.stats.compute_count == 2
    assert engine.stats.cache_hit_count == 0
