from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Any


FIELD_RULES: list[tuple[str, str, str]] = [
    (r"^(?:WBS|WBS编码|工作分解结构编码)$|_+(?:WBS|WBS编码|工作分解结构编码)$", "wbs_code", "text"),
    (r"^(?:任务编码|清单编码|编号|项目编码|task.?code)$", "task_code", "text"),
    (r"工作内容|施工内容|施工项|工序|工序内容|任务名称|子项|分项工程", "task_name", "text"),
    (r"父级|上级", "parent_task_name", "text"),
    (r"^(?:楼层|层|所在楼层|施工楼层|楼层/区域|楼层区域)$", "floor", "text"),
    (r"区域", "area", "text"),
    (r"^(?:施工单位|分包单位|责任单位|单位名称|承包单位)$", "construction_unit", "text"),
    (r"楼栋|单体|楼号|楼座", "building", "text"),
    (r"专业", "discipline", "text"),
    (r"系统", "system_name", "text"),
    (r"^(?:单位|计量单位|工程量单位|数量单位)$", "unit", "text"),
    (r"工程量|总工程量|设计量|合同量|清单量|总量|总数量", "total_quantity", "number"),
    (r"本周完成|本日完成|本月完成|本期完成|当期完成", "period_quantity", "number"),
    (r"累计完成量|累计完成|已完成量|完成工程量|累计工程量", "cumulative_quantity", "number"),
    (r"实际完成量", "actual_quantity", "number"),
    (r"剩余", "remaining_quantity", "number"),
    (r"计划完成量|应完成量|目标完成量", "planned_quantity", "number"),
    (r"计划进度|计划完成进度|目标进度|应完成进度|应完成率|本期计划进度|计划百分比|计划完成率|计划完成比例|计划比例|目标完成率", "planned_percent", "percent"),
    (
        r"实际进度|实际完成进度|完成进度|形象进度|实际形象进度|累计进度|累计完成率|完成百分比|完成比例|完工率|完工进度|当前进度|施工进度|实际完成情况|完成情况|进度百分比|实际完成率",
        "actual_percent",
        "percent",
    ),
    (r"上报完成率", "reported_percent", "percent"),
    (r"计划开始", "planned_start_date", "date"),
    (r"计划完成|计划结束", "planned_finish_date", "date"),
    (r"实际开始", "actual_start_date", "date"),
    (r"实际完成日期|实际完成时间|实际结束|完成日期|完成时间", "actual_finish_date", "date"),
    (r"^(?:权重|任务权重|项目权重|统计权重|占比|weight)$", "weight", "number"),
    (r"权重", "weight", "number"),
    (r"产值|金额", "value_amount", "currency"),
    (r"状态", "status", "text"),
    (r"备注|说明", "remark", "text"),
    (r"责任人|负责人|责任工程师|班组|施工班组", None, "unknown"),
    (r"名称|清单名称", "task_name", "text"),
    (r"完成率", "actual_percent", "percent"),
]

SYSTEM_FIELD_TYPES: dict[str, str] = {}
for _, field_name, field_type in FIELD_RULES:
    if field_name and field_name not in SYSTEM_FIELD_TYPES:
        SYSTEM_FIELD_TYPES[field_name] = field_type


def normalize_column_name(value: str) -> str:
    """Normalize a header for rule matching while preserving Chinese words."""

    if not value:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[()\[\]{}（）【】《》<>]", "", text)
    text = text.replace("％", "%")
    return text


def default_field_type(system_field: str | None) -> str:
    if not system_field:
        return "unknown"
    return SYSTEM_FIELD_TYPES.get(system_field, "unknown")


def detect_column(column_name: str, sample_values: Iterable[Any] | None = None) -> dict[str, str | bool | None]:
    normalized = normalize_column_name(column_name)
    for pattern, system_field, field_type in FIELD_RULES:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            result: dict[str, str | bool | None] = {"recommended_field": system_field, "field_type": field_type}
            return _apply_sample_hints(normalized, sample_values, result)
    return _apply_sample_hints(normalized, sample_values, {"recommended_field": None, "field_type": "unknown"})


def _apply_sample_hints(
    normalized_name: str,
    sample_values: Iterable[Any] | None,
    result: dict[str, str | bool | None],
) -> dict[str, str | bool | None]:
    samples = _clean_samples(sample_values)
    if not samples:
        return result

    sample_type = _infer_sample_type(samples)
    if result.get("field_type") in (None, "unknown") and sample_type != "unknown":
        result["field_type"] = sample_type
        result["sample_reason"] = f"样本值更像{_sample_type_label(sample_type)}。"

    recommended = result.get("recommended_field")
    if recommended:
        return result

    inferred_field = _infer_field_from_name_and_samples(normalized_name, sample_type, samples)
    if inferred_field:
        result["recommended_field"] = inferred_field
        result["field_type"] = default_field_type(inferred_field)
        result["sample_reason"] = _sample_field_reason(inferred_field, sample_type)
        result["needs_review"] = _needs_review_for_sample_inference(inferred_field, normalized_name)
    return result


def _clean_samples(sample_values: Iterable[Any] | None, limit: int = 20) -> list[str]:
    if sample_values is None:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in sample_values:
        if value is None:
            continue
        text = str(value).strip()
        if not text or text.lower() == "nan":
            continue
        if text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _infer_sample_type(samples: list[str]) -> str:
    non_empty_count = len(samples)
    if non_empty_count == 0:
        return "unknown"

    percent_count = sum(1 for value in samples if _looks_percent(value))
    date_count = sum(1 for value in samples if _looks_date(value))
    currency_count = sum(1 for value in samples if _looks_currency(value))
    number_count = sum(1 for value in samples if _looks_number(value))

    threshold = max(1, int(non_empty_count * 0.6))
    if percent_count >= threshold:
        return "percent"
    if date_count >= threshold:
        return "date"
    if currency_count >= threshold:
        return "currency"
    if number_count >= threshold:
        return "number"
    return "text"


def _infer_field_from_name_and_samples(normalized_name: str, sample_type: str, samples: list[str]) -> str | None:
    if sample_type == "percent":
        if any(keyword in normalized_name for keyword in ("计划", "应", "目标")):
            return "planned_percent"
        if any(keyword in normalized_name for keyword in ("上报", "填报", "报送")):
            return "reported_percent"
        if any(keyword in normalized_name for keyword in ("实际", "当前", "完成", "完工", "进度", "形象", "累计")):
            return "actual_percent"

    if sample_type == "date":
        if "计划" in normalized_name and any(keyword in normalized_name for keyword in ("开始", "开工")):
            return "planned_start_date"
        if "计划" in normalized_name and any(keyword in normalized_name for keyword in ("完成", "结束", "完工")):
            return "planned_finish_date"
        if "实际" in normalized_name and any(keyword in normalized_name for keyword in ("开始", "开工")):
            return "actual_start_date"
        if "实际" in normalized_name and any(keyword in normalized_name for keyword in ("完成", "结束", "完工")):
            return "actual_finish_date"

    if sample_type in {"number", "currency"}:
        if any(keyword in normalized_name for keyword in ("权重", "占比")):
            return "weight"
        if sample_type == "currency" or any(keyword in normalized_name for keyword in ("产值", "金额", "造价")):
            return "value_amount"
        if any(keyword in normalized_name for keyword in ("累计", "已完成")) and "量" in normalized_name:
            return "cumulative_quantity"
        if any(keyword in normalized_name for keyword in ("本期", "本周", "本月", "当期")) and "完成" in normalized_name:
            return "period_quantity"
        if any(keyword in normalized_name for keyword in ("总", "设计", "合同", "清单")) and "量" in normalized_name:
            return "total_quantity"

    if sample_type == "text":
        if _looks_like_floor_values(samples) and any(keyword in normalized_name for keyword in ("层", "楼层", "位置", "部位")):
            return "floor"
        if _looks_like_building_values(samples) and any(keyword in normalized_name for keyword in ("楼", "栋", "单体", "位置", "部位")):
            return "building"
        if _looks_like_discipline_values(samples) and any(keyword in normalized_name for keyword in ("专业", "类别", "系统")):
            return "discipline"

    return None


def _looks_percent(value: str) -> bool:
    text = value.strip()
    if "%" in text or "％" in text:
        return _looks_number(text.replace("%", "").replace("％", ""))
    try:
        number = float(text)
    except ValueError:
        return False
    return 0 <= number <= 1


def _looks_number(value: str) -> bool:
    text = value.strip().replace(",", "").replace("，", "").replace("%", "").replace("％", "")
    if not text:
        return False
    try:
        float(text)
    except ValueError:
        return False
    return True


def _looks_currency(value: str) -> bool:
    text = value.strip()
    return any(symbol in text for symbol in ("¥", "￥", "元", "万元")) and _looks_number(
        text.replace("¥", "").replace("￥", "").replace("万元", "").replace("元", "")
    )


def _looks_date(value: str) -> bool:
    text = value.strip()
    if re.fullmatch(r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?", text):
        return True
    if re.fullmatch(r"\d{1,2}[-/.]\d{1,2}", text):
        return True
    return False


def _looks_like_floor_values(samples: list[str]) -> bool:
    hits = sum(1 for value in samples if re.search(r"^(?:b\d+|地下.*层|\d+f|\d+层|[负-]?\d+)$", normalize_column_name(value), flags=re.IGNORECASE))
    return hits >= max(1, int(len(samples) * 0.6))


def _looks_like_building_values(samples: list[str]) -> bool:
    hits = sum(1 for value in samples if re.search(r"^(?:[a-z]?\d+号?楼|[a-z]\d+|[a-z座栋]|\d+号楼)$", normalize_column_name(value), flags=re.IGNORECASE))
    return hits >= max(1, int(len(samples) * 0.6))


def _looks_like_discipline_values(samples: list[str]) -> bool:
    disciplines = ("机电", "消防", "智能化", "土建", "装修", "暖通", "给排水", "电气", "弱电", "强电")
    hits = sum(1 for value in samples if any(keyword in value for keyword in disciplines))
    return hits >= max(1, int(len(samples) * 0.6))


def _sample_type_label(sample_type: str) -> str:
    return {
        "percent": "百分比",
        "date": "日期",
        "currency": "金额",
        "number": "数值",
        "text": "文本",
    }.get(sample_type, "未知类型")


def _sample_field_reason(system_field: str, sample_type: str) -> str:
    return f"列名较模糊，但样本值呈现{_sample_type_label(sample_type)}特征，结合列名语义推荐映射为 {system_field}。"


def _needs_review_for_sample_inference(system_field: str, normalized_name: str) -> bool:
    if system_field in {"planned_percent", "actual_percent", "reported_percent"}:
        return not any(keyword in normalized_name for keyword in ("计划", "应", "目标", "实际", "当前", "上报", "完成", "完工"))
    return False
