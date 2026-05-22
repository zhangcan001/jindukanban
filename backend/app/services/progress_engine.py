from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

from app.models.calculation_profile import CalculationProfile
from app.models.import_batch import ImportBatch
from app.models.progress_item import ProgressItem
from app.services.progress_calculator import calculate_progress_fields


@dataclass
class ProgressComputeStats:
    """便于排查重复计算的统计；engine.stats 暴露给上层做调试 / 性能指标。"""

    compute_count: int = 0
    cache_hit_count: int = 0


_CALCULATED_FIELDS = (
    "actual_percent",
    "planned_percent",
    "imported_planned_percent",
    "time_planned_percent",
    "progress_deviation",
    "schedule_phase",
    "status",
)


@dataclass
class ProgressEngine:
    """ProgressItem 衍生字段的统一计算入口。

    用法（推荐在一次 HTTP 请求内复用同一个 engine 实例）：
        engine = ProgressEngine(profile=profile)
        engine.apply(items, batch=batch)            # 按 batch.data_date 重算并写回
        engine.compute(item, data_date=...)         # 只取计算结果，不写回

    设计要点：
    1. **profile 感知**——把 calculation_profile 注入 calculate_progress_fields，
       使 calculation_profile 的滞后阈值在 dashboard 重算路径上真正生效。
    2. **请求级缓存**——同一 engine 内 (item_id, reference_date) 不重复计算；
       缓存不跨实例 / 不持久化，避免阈值变更后吃到陈旧数据。
    3. **就地写回**——保留原 apply_time_based_progress 的语义（mutate items），
       上层 service 不必改用法。
    """

    profile: CalculationProfile | None = None
    default_data_date: date | None = None
    _cache: dict[tuple[int, date | None], dict] = field(default_factory=dict, init=False, repr=False)
    stats: ProgressComputeStats = field(default_factory=ProgressComputeStats)

    def compute(
        self,
        item: ProgressItem,
        data_date: date | None = None,
        previous_item: ProgressItem | None = None,
    ) -> dict:
        effective_date = data_date if data_date is not None else self.default_data_date
        cache_key = (item.id if item.id is not None else id(item), effective_date)
        # previous_item 改变会影响 current_period_*，所以 previous_item 不为空时直接重算不走缓存
        if previous_item is None and cache_key in self._cache:
            self.stats.cache_hit_count += 1
            return self._cache[cache_key]
        result = calculate_progress_fields(
            _item_to_values(item),
            self.profile,
            effective_date,
            previous_item,
        )
        if previous_item is None:
            self._cache[cache_key] = result
        self.stats.compute_count += 1
        return result

    def apply(
        self,
        items: Iterable[ProgressItem],
        *,
        batch: ImportBatch | None = None,
        data_date: date | None = None,
    ) -> list[ProgressItem]:
        reference_date = data_date if data_date is not None else (
            (batch.data_date if batch is not None else None) or self.default_data_date or date.today()
        )
        items_list = list(items)
        for item in items_list:
            calculated = self.compute(item, reference_date)
            for field_name in _CALCULATED_FIELDS:
                if field_name in calculated:
                    setattr(item, field_name, calculated[field_name])
        return items_list

    def invalidate(self) -> None:
        """阈值或 profile 修改后调用——清空缓存，下次 compute 重算。"""

        self._cache.clear()


def _item_to_values(item: ProgressItem) -> dict:
    """ProgressItem ORM → calculate_progress_fields 入参字典。

    包含 discipline/floor/building 是为了让 resolve_delay_thresholds() 能命中维度覆盖。
    """

    return {
        "total_quantity": item.total_quantity,
        "planned_quantity": item.planned_quantity,
        "period_quantity": item.period_quantity,
        "cumulative_quantity": item.cumulative_quantity,
        "actual_quantity": item.actual_quantity,
        "remaining_quantity": item.remaining_quantity,
        "planned_percent": item.planned_percent,
        "imported_planned_percent": item.imported_planned_percent,
        "actual_percent": item.actual_percent,
        "reported_percent": item.reported_percent,
        "planned_start_date": item.planned_start_date,
        "planned_finish_date": item.planned_finish_date,
        "discipline": item.discipline,
        "floor": item.floor,
        "building": item.building,
    }
