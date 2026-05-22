from app.services.value_normalizer import normalize_value


def test_normalize_floor_and_discipline_aliases() -> None:
    assert normalize_value("floor", "地下1层") == "B1层"
    assert normalize_value("floor", "负一层") == "B1层"
    assert normalize_value("discipline", "电") == "电气"
    assert normalize_value("discipline", "强电") == "电气"
    assert normalize_value("discipline", "水") == "给排水"
    assert normalize_value("discipline", "给排水") == "给排水"
