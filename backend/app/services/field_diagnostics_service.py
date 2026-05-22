from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.models.import_batch import ImportBatch
from app.models.progress_item import ProgressItem
from app.schemas.mapping import FieldMapping
from app.services.analytics_service import available_calculation_methods, has_mixed_units, item_units, recommended_calculation_method


FIELD_LABELS = {
    "task_name": "施工项",
    "total_quantity": "总工程量",
    "cumulative_quantity": "累计完成量",
    "actual_percent": "实际完成率",
    "planned_start_date": "计划开始日期",
    "planned_finish_date": "计划完成日期",
    "building": "楼栋",
    "floor": "楼层",
    "discipline": "专业",
    "system_name": "系统",
    "construction_unit": "施工单位",
    "weight": "权重",
    "value_amount": "产值 / 金额",
    "unit": "单位",
    "remark": "备注",
    "responsible_person": "责任人",
    "responsible_unit": "责任单位",
}

CORE_FIELDS = {"task_name", "total_quantity", "cumulative_quantity", "actual_percent", "planned_start_date", "planned_finish_date"}
GROUP_FIELDS = {"building", "floor", "discipline", "system_name", "construction_unit"}
ENHANCED_FIELDS = {"weight", "value_amount", "unit"}
AUX_FIELDS = {"remark", "responsible_person", "responsible_unit"}
STAT_FIELDS = {"total_quantity", "cumulative_quantity", "actual_percent", "planned_percent", "weight", "value_amount", "unit"}
DELAY_FIELDS = {"planned_start_date", "planned_finish_date", "planned_percent", "actual_percent", "total_quantity", "cumulative_quantity"}


def field_role(system_field: str | None) -> str:
    if system_field in CORE_FIELDS:
        return "核心进度字段"
    if system_field in GROUP_FIELDS:
        return "分组字段"
    if system_field in ENHANCED_FIELDS:
        return "统计增强字段"
    if system_field in AUX_FIELDS:
        return "辅助字段"
    return "未分组字段"


def field_impact(system_field: str | None) -> dict[str, bool]:
    return {
        "is_required": system_field == "task_name",
        "affects_statistics": bool(system_field in STAT_FIELDS or system_field in GROUP_FIELDS),
        "affects_delay": bool(system_field in DELAY_FIELDS),
    }


def explain_mapping(column_name: str, recommended_field: str | None, *, multi_header: bool = False, from_template: bool = False) -> dict[str, Any]:
    if from_template:
        match_type = "历史模板匹配"
    elif recommended_field is None:
        match_type = "未识别"
    elif multi_header and "_" in column_name:
        match_type = "多行表头组合匹配"
    elif _exact_alias_hit(column_name, recommended_field):
        match_type = "精确别名匹配"
    else:
        match_type = "模糊关键词匹配"
    confidence = "高" if match_type in {"精确别名匹配", "历史模板匹配"} else ("中" if recommended_field else "低")
    return {
        "match_type": match_type,
        "confidence": confidence,
        "reason": _mapping_reason(column_name, recommended_field, match_type),
        "field_role": field_role(recommended_field),
        **field_impact(recommended_field),
    }


def build_parse_field_diagnostics(batch: ImportBatch, columns: list[dict[str, Any]]) -> dict[str, Any]:
    mappings = [
        FieldMapping(
            excel_column_name=str(column.get("name") or ""),
            recommended_field=column.get("recommended_field"),
            system_field_name=column.get("recommended_field"),
            field_type=str(column.get("field_type") or "unknown"),
            is_dimension=bool(column.get("is_dimension")),
            is_metric=bool(column.get("is_metric")),
            save_to_extra=bool(column.get("save_to_extra", True)),
            sort_order=index,
        )
        for index, column in enumerate(columns)
    ]
    return build_mapping_diagnostics(batch, mappings, items=[])


def build_mapping_diagnostics(batch: ImportBatch, mappings: list[FieldMapping], items: Iterable[ProgressItem] | None = None) -> dict[str, Any]:
    item_list = list(items or [])
    mapped_fields = {mapping.system_field_name for mapping in mappings if mapping.system_field_name}
    recognized = []
    for mapping in mappings:
        mapped_field = mapping.system_field_name or mapping.recommended_field
        explanation = explain_mapping(
            mapping.excel_column_name,
            mapped_field,
            multi_header=batch.multi_header,
        )
        if mapping.match_type:
            explanation["match_type"] = mapping.match_type
        if mapping.confidence:
            explanation["confidence"] = mapping.confidence
        if mapping.reason:
            explanation["reason"] = mapping.reason
        if mapping.field_role:
            explanation["field_role"] = mapping.field_role
        explanation["is_required"] = bool(mapping.is_required or explanation["is_required"])
        explanation["affects_statistics"] = bool(mapping.affects_statistics or explanation["affects_statistics"])
        explanation["affects_delay"] = bool(mapping.affects_delay or explanation["affects_delay"])
        recognized.append(
            {
                "excel_column_name": mapping.excel_column_name,
                "system_field_name": mapping.system_field_name,
                "recommended_field": mapping.recommended_field,
                "field_type": mapping.field_type,
                **explanation,
            }
        )

    missing_core = sorted(field for field in CORE_FIELDS if field not in mapped_fields)
    field_impacts = _field_impacts(mapped_fields)
    available_methods = _available_methods_for_mapping(mapped_fields, item_list)
    recommended = _recommended_method_for_mapping(mapped_fields, item_list)
    unit = _unit_diagnostics(mapped_fields, item_list)
    weight = _weight_diagnostics(mapped_fields, item_list)
    completeness = _completeness(mapped_fields, item_list)
    capabilities = _dashboard_capabilities(mapped_fields, item_list)
    recognized_count = sum(1 for mapping in mappings if mapping.system_field_name)
    quality = round(recognized_count / len(mappings), 4) if mappings else 0
    return {
        "field_mapping_quality": {
            "recognized_count": recognized_count,
            "total_count": len(mappings),
            "score": quality,
            "label": "高" if quality >= 0.8 else ("中" if quality >= 0.5 else "低"),
        },
        "recognized_fields": recognized,
        "missing_core_fields": missing_core,
        "field_impacts": field_impacts,
        "available_calculation_methods": available_methods,
        "recommended_calculation_method": recommended,
        "recommended_calculation_method_name": _method_name(recommended),
        "recommended_reason": _recommended_reason(recommended, available_methods),
        "unit_diagnostics": unit,
        "weight_diagnostics": weight,
        "field_completeness_summary": completeness,
        "dashboard_capabilities": capabilities,
    }


def build_item_diagnostics(items: list[ProgressItem]) -> dict[str, Any]:
    fields = _fields_from_items(items)
    return build_mapping_diagnostics(_dummy_batch(), [FieldMapping(excel_column_name=field, system_field_name=field, recommended_field=field) for field in sorted(fields)], items)


def _dummy_batch() -> ImportBatch:
    return ImportBatch(project_id=0, file_name="", multi_header=False)


def _fields_from_items(items: list[ProgressItem]) -> set[str]:
    checks = {
        "task_name": lambda item: item.task_name,
        "total_quantity": lambda item: item.total_quantity,
        "cumulative_quantity": lambda item: item.cumulative_quantity,
        "actual_percent": lambda item: item.actual_percent,
        "planned_start_date": lambda item: item.planned_start_date,
        "planned_finish_date": lambda item: item.planned_finish_date,
        "building": lambda item: item.building,
        "floor": lambda item: item.floor,
        "discipline": lambda item: item.discipline,
        "system_name": lambda item: item.system_name,
        "construction_unit": lambda item: item.construction_unit,
        "weight": lambda item: item.weight,
        "value_amount": lambda item: item.value_amount,
        "unit": lambda item: item.unit,
    }
    return {field for field, getter in checks.items() if any(getter(item) not in {None, ""} for item in items)}


def _available_methods_for_mapping(mapped_fields: set[str | None], items: list[ProgressItem]) -> list[dict[str, Any]]:
    if items:
        rows = available_calculation_methods(items)
    else:
        has_weight = "weight" in mapped_fields
        has_value = "value_amount" in mapped_fields
        has_quantity = {"total_quantity", "cumulative_quantity"}.issubset(mapped_fields)
        has_percent = "actual_percent" in mapped_fields
        rows = [
            {"code": "weighted_percent", "name": "权重统计", "available": has_weight, "reason": "检测到权重字段" if has_weight else "未检测到权重字段"},
            {"code": "value_weighted_percent", "name": "产值加权统计", "available": has_value, "reason": "检测到产值字段" if has_value else "未检测到产值字段"},
            {"code": "quantity_percent", "name": "工程量统计", "available": has_quantity, "reason": "检测到总工程量和累计完成量" if has_quantity else "未检测到完整工程量字段"},
            {"code": "percent_average", "name": "进度百分比平均", "available": has_percent, "reason": "检测到实际完成率字段" if has_percent else "未检测到实际完成率字段"},
            {"code": "task_average", "name": "任务平均统计", "available": True, "reason": "兜底统计口径"},
        ]
    recommended = _recommended_method_for_mapping(mapped_fields, items)
    for row in rows:
        row["recommended"] = row["code"] == recommended
        if row["code"] == "quantity_percent" and row.get("available") and _mapping_has_mixed_units(mapped_fields, items):
            row["warning"] = "当前数据包含多种单位，直接汇总工程量可能失真，建议使用权重统计或百分比平均。"
        if row["code"] == "quantity_percent" and row.get("warning"):
            row["not_recommended_reason"] = row["warning"]
        elif row["available"] and not row["recommended"]:
            row["not_recommended_reason"] = "存在优先级更高且更适合当前数据的统计口径。"
        elif not row["available"]:
            row["not_recommended_reason"] = row["reason"]
    return rows


def _recommended_method_for_mapping(mapped_fields: set[str | None], items: list[ProgressItem]) -> str:
    if items:
        return recommended_calculation_method(items)
    if "weight" in mapped_fields:
        return "weighted_percent"
    if "value_amount" in mapped_fields:
        return "value_weighted_percent"
    if {"total_quantity", "cumulative_quantity"}.issubset(mapped_fields):
        return "quantity_percent"
    if "actual_percent" in mapped_fields:
        return "percent_average"
    return "task_average"


def _mapping_has_mixed_units(mapped_fields: set[str | None], items: list[ProgressItem]) -> bool:
    return "unit" in mapped_fields and has_mixed_units(items)


def _unit_diagnostics(mapped_fields: set[str | None], items: list[ProgressItem]) -> dict[str, Any]:
    units = item_units(items) if items else []
    mixed = has_mixed_units(items) if items else False
    return {
        "unit_field_exists": "unit" in mapped_fields or bool(units),
        "unit_list": units,
        "is_mixed": mixed,
        "message": "当前数据包含多种单位，直接汇总工程量可能失真，建议使用权重统计或百分比平均。" if mixed else None,
    }


def _weight_diagnostics(mapped_fields: set[str | None], items: list[ProgressItem]) -> dict[str, Any]:
    weights = [item.weight for item in items if item.weight is not None and item.weight > 0]
    missing = sum(1 for item in items if item.weight is None) if items else 0
    return {
        "weight_field_exists": "weight" in mapped_fields or bool(weights),
        "weight_total": round(sum(weights), 6) if weights else None,
        "valid_weight_task_count": len(weights),
        "missing_weight_task_count": missing,
    }


def _completeness(mapped_fields: set[str | None], items: list[ProgressItem]) -> dict[str, Any]:
    total = len(items)
    if total:
        return {
            "quantity_field_complete_rate": _rate(items, lambda item: item.total_quantity is not None and item.cumulative_quantity is not None),
            "plan_date_complete_rate": _rate(items, lambda item: item.planned_start_date is not None and item.planned_finish_date is not None),
            "actual_percent_complete_rate": _rate(items, lambda item: item.actual_percent is not None),
        }
    return {
        "quantity_field_complete_rate": 1.0 if {"total_quantity", "cumulative_quantity"}.issubset(mapped_fields) else 0.0,
        "plan_date_complete_rate": 1.0 if {"planned_start_date", "planned_finish_date"}.issubset(mapped_fields) else 0.0,
        "actual_percent_complete_rate": 1.0 if "actual_percent" in mapped_fields else 0.0,
    }


def _dashboard_capabilities(mapped_fields: set[str | None], items: list[ProgressItem]) -> dict[str, Any]:
    has = lambda field: field in mapped_fields or any(getattr(item, field, None) not in {None, ""} for item in items)
    methods = {row["code"]: row for row in _available_methods_for_mapping(mapped_fields, items)}
    return {
        "overview": {"available": True, "reason": "总体视图可基于已导入任务展示。"},
        "discipline_view": {"available": has("discipline"), "reason": "未识别专业字段。" if not has("discipline") else "已识别专业字段。"},
        "building_view": {"available": has("building"), "reason": "当前批次未识别到楼栋字段，楼栋视图不可用。请在导入字段映射中将“楼号 / 楼栋 / 楼座”等字段映射为楼栋。" if not has("building") else "已识别楼栋字段。"},
        "floor_heatmap": {"available": has("floor"), "reason": "当前批次未识别到楼层字段，楼层热力图不可用。请在导入字段映射中将“层 / 楼层 / 施工楼层”等字段映射为楼层。" if not has("floor") else "已识别楼层字段。"},
        "construction_unit_filter": {"available": has("construction_unit"), "reason": "未识别施工单位字段。" if not has("construction_unit") else "已识别施工单位字段。"},
        "weighted_percent": {"available": bool(methods["weighted_percent"]["available"]), "reason": str(methods["weighted_percent"]["reason"])},
        "quantity_percent": {"available": bool(methods["quantity_percent"]["available"]), "reason": str(methods["quantity_percent"].get("not_recommended_reason") or methods["quantity_percent"]["reason"])},
        "percent_average": {"available": bool(methods["percent_average"]["available"]), "reason": str(methods["percent_average"]["reason"])},
    }


def _field_impacts(mapped_fields: set[str | None]) -> list[dict[str, str]]:
    impacts = []
    rules = {
        "task_name": "无法生成有效进度明细。",
        "planned_start_date": "无法按计划日期计算应完成进度，只能使用导入的计划完成率或任务平均。",
        "planned_finish_date": "无法按计划日期计算应完成进度，只能使用导入的计划完成率或任务平均。",
        "total_quantity": "无法按工程量计算实际完成率，将尝试使用实际完成率字段。",
        "cumulative_quantity": "无法按工程量计算实际完成率，将尝试使用实际完成率字段。",
        "weight": "无法使用权重统计，将推荐百分比平均或任务平均。",
        "building": "楼栋视图将不可用或不完整。",
        "floor": "楼层视图将不可用或不完整。",
    }
    for field, message in rules.items():
        if field not in mapped_fields:
            impacts.append({"field": field, "field_label": FIELD_LABELS.get(field, field), "impact": message})
    return impacts


def _rate(items: list[ProgressItem], predicate) -> float:
    return round(sum(1 for item in items if predicate(item)) / len(items), 4) if items else 0.0


def _exact_alias_hit(column_name: str, system_field: str | None) -> bool:
    aliases = {
        "cumulative_quantity": {"累计完成量", "累计完成", "已完成量", "完成工程量", "累计工程量"},
        "actual_percent": {"实际完成率", "实际进度", "完成进度", "完成百分比"},
        "planned_percent": {"计划完成率", "计划进度", "应完成率"},
        "task_name": {"工作内容", "施工内容", "施工项", "任务名称"},
        "building": {"楼栋", "楼号", "楼座"},
        "floor": {"楼层", "层", "施工楼层"},
        "weight": {"权重", "任务权重", "统计权重"},
    }
    normalized = column_name.replace(" ", "").split("_")[-1]
    return normalized in aliases.get(system_field or "", set())


def _mapping_reason(column_name: str, system_field: str | None, match_type: str) -> str:
    if not system_field:
        return "未命中系统内置别名或关键词，默认保存为扩展字段。"
    label = FIELD_LABELS.get(system_field, system_field)
    if match_type == "精确别名匹配":
        return f"命中别名“{column_name}”，该字段识别为{label}。"
    if match_type == "多行表头组合匹配":
        return f"由多行表头组合后命中{label}相关关键词。"
    if match_type == "历史模板匹配":
        return f"根据历史字段映射模板匹配为{label}。"
    return f"列名包含{label}相关关键词，系统推荐映射为{system_field}。"


def _method_name(code: str) -> str:
    return {
        "weighted_percent": "权重统计",
        "value_weighted_percent": "产值加权统计",
        "quantity_percent": "工程量统计",
        "percent_average": "进度百分比平均",
        "task_average": "任务平均统计",
    }.get(code, code)


def _recommended_reason(code: str, methods: list[dict[str, Any]]) -> str:
    row = next((item for item in methods if item["code"] == code), None)
    return str(row.get("reason")) if row else "按当前字段完整度自动推荐。"
