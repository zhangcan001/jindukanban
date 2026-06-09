from __future__ import annotations

from datetime import date, datetime, time, timedelta
import math
import re
from typing import Any


EMPTY_DATE_MARKERS = {"", "--", "/", "nan", "nat", "none", "null"}


def normalize_date(value: Any) -> date | None:
    """Normalize common engineering Excel date values to a date."""
    if is_empty_date_value(value):
        return None

    if _is_pandas_timestamp(value):
        if getattr(value, "tzinfo", None) is not None:
            value = value.to_pydatetime()
        return value.date()

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, time):
        return None

    if isinstance(value, int | float) and not isinstance(value, bool):
        if isinstance(value, float) and math.isnan(value):
            return None
        excel_value = _from_excel_serial(value)
        if excel_value is None:
            return None
        if isinstance(excel_value, datetime):
            return excel_value.date()
        if isinstance(excel_value, date):
            return excel_value
        return None

    text = str(value).strip()
    if not text:
        return None

    normalized_text = _normalize_date_text(text)
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y.%m.%d %H:%M:%S"):
        try:
            return datetime.strptime(normalized_text, fmt).date()
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(normalized_text).date()
    except ValueError:
        return None


def is_empty_date_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    text = str(value).strip().lower()
    return text in EMPTY_DATE_MARKERS


def _normalize_date_text(text: str) -> str:
    normalized = text.strip()
    chinese = re.fullmatch(r"(\d{4})年(\d{1,2})月(\d{1,2})日", normalized)
    if chinese:
        year, month, day = chinese.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return normalized


def _from_excel_serial(value: int | float) -> datetime | None:
    number = float(value)
    if number < 0 or 0 <= number < 1:
        return None
    day, fraction = divmod(number, 1)
    if 0 < number < 60:
        day += 1
    try:
        return datetime(1899, 12, 30) + timedelta(days=int(day), seconds=round(fraction * 86400))
    except (OverflowError, ValueError):
        return None


def _is_pandas_timestamp(value: Any) -> bool:
    return value.__class__.__module__.startswith("pandas") and value.__class__.__name__ == "Timestamp"
