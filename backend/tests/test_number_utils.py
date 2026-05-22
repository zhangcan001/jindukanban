from app.utils.number_utils import normalize_percent


def test_normalize_percent_accepts_common_percent_formats() -> None:
    for value in (0.58, "0.58", 58, "58", "58%"):
        assert normalize_percent(value) == 58.0


def test_normalize_percent_accepts_real_progress_values() -> None:
    assert normalize_percent(0.1) == 10.0
    assert normalize_percent("未开始") == 0.0


def test_normalize_percent_keeps_out_of_range_values_for_validator_warning() -> None:
    assert normalize_percent("120%") == 120.0


def test_normalize_percent_returns_none_for_invalid_values() -> None:
    assert normalize_percent("not-a-percent") is None
