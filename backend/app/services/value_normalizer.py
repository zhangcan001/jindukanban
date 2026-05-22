from __future__ import annotations

import re
from typing import Any


NORMALIZED_FIELDS = {"area", "building", "floor", "discipline", "system_name", "status"}

FLOOR_RULES = {
    "负一层": "B1层",
    "地下1层": "B1层",
    "地下一层": "B1层",
    "-1F": "B1层",
    "负二层": "B2层",
    "地下2层": "B2层",
    "地下二层": "B2层",
    "-2F": "B2层",
    "1F": "1层",
    "一层": "1层",
    "第1层": "1层",
    "2F": "2层",
    "二层": "2层",
    "第2层": "2层",
}

DISCIPLINE_RULES = {
    "水": "给排水",
    "给排水": "给排水",
    "给水排水": "给排水",
    "给排水专业": "给排水",
    "电": "电气",
    "电气": "电气",
    "电气专业": "电气",
    "强电": "电气",
    "暖通": "暖通",
    "通风空调": "暖通",
    "空调水": "暖通",
    "空调风": "暖通",
    "消防": "消防",
    "消防水": "消防",
    "消防电": "消防",
    "弱电": "智能化",
    "智能化": "智能化",
    "智能化系统": "智能化",
}


def normalize_value(field_name: str, value: Any) -> Any:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None

    if field_name == "floor":
        return FLOOR_RULES.get(text, _normalize_floor_pattern(text))
    if field_name == "discipline":
        return DISCIPLINE_RULES.get(text, text)
    if field_name in NORMALIZED_FIELDS:
        return text
    return value


def _normalize_floor_pattern(text: str) -> str:
    basement = re.fullmatch(r"(?:B|b)(\d+)(?:层|F|f)?", text)
    if basement:
        return f"B{basement.group(1)}层"

    above_ground = re.fullmatch(r"(\d+)(?:F|f|层)?", text)
    if above_ground:
        return f"{above_ground.group(1)}层"

    return text

