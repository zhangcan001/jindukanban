from __future__ import annotations

import math
from typing import Any


PERCENT_TEXT_VALUES = {
    "未开始": 0.0,
    "未开工": 0.0,
    "未施工": 0.0,
    "未完成": 0.0,
    "已完成": 100.0,
    "完成": 100.0,
    "已完工": 100.0,
    "完工": 100.0,
    "完成施工": 100.0,
}


def normalize_percent(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        if isinstance(value, float) and math.isnan(value):
            return None
        number = float(value)
    else:
        text = str(value).strip().replace(",", "")
        if not text:
            return None
        compact_text = "".join(text.split())
        if compact_text in PERCENT_TEXT_VALUES:
            return PERCENT_TEXT_VALUES[compact_text]
        if text.endswith("%"):
            text = text[:-1].strip()
        try:
            number = float(text)
        except ValueError:
            return None

    if 0 < number <= 1:
        return round(number * 100, 4)
    return round(number, 4)
