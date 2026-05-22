from datetime import date, datetime, time

import pandas as pd
from openpyxl.utils.datetime import to_excel

from app.utils.date_utils import normalize_date


def test_normalize_date_accepts_common_engineering_excel_formats() -> None:
    expected = date(2026, 5, 1)
    values = [
        "2026-05-01",
        "2026/05/01",
        "2026.05.01",
        "2026年5月1日",
        "2026年05月01日",
        "2026-05-01 00:00:00",
        "2026/5/1",
        "2026.5.1",
        datetime(2026, 5, 1, 0, 0, 0),
        date(2026, 5, 1),
        pd.Timestamp("2026-05-01"),
        to_excel(expected),
    ]

    for value in values:
        assert normalize_date(value) == expected


def test_normalize_date_returns_none_for_empty_or_invalid_values() -> None:
    for value in (None, "", " ", "--", "/", float("nan")):
        assert normalize_date(value) is None

    for value in ("日期错误", "abc", "2026-99-99", "2026/13/01", time(8, 30), 0.25):
        assert normalize_date(value) is None
