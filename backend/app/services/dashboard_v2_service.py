from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.project import Project
from app.schemas.analytics import DashboardV2Response, DashboardV2Scope
from app.services.dashboard_unified_service import build_dashboard_unified
from app.services.analytics_service import list_items
from app.services.field_diagnostics_service import build_item_diagnostics

VALID_VIEW_MODES = {"overview", "discipline", "building"}


def build_dashboard_v2(
    db: Session,
    project: Project,
    *,
    view_mode: str = "overview",
    data_date: date | None = None,
    import_group_id: str | None = None,
    batch_id: int | None = None,
    sheet_name: str | None = None,
    construction_unit: str | None = None,
    building: str | None = None,
    floor: str | None = None,
    discipline: str | None = None,
    system_name: str | None = None,
    status: str | None = None,
    calculation_method: str | None = None,
    baseline_plan_id: int | None = None,
    calculation_profile_id: int | None = None,
) -> DashboardV2Response:
    mode = view_mode if view_mode in VALID_VIEW_MODES else "overview"
    unified = build_dashboard_unified(
        db,
        project,
        data_date=data_date,
        import_group_id=import_group_id,
        batch_id=batch_id,
        sheet_name=sheet_name,
        construction_unit=construction_unit,
        building=building,
        floor=floor,
        discipline=discipline,
        system_name=system_name,
        status=status,
        calculation_method=calculation_method,
        baseline_plan_id=baseline_plan_id,
        calculation_profile_id=calculation_profile_id,
    )
    context = dict(unified.calculation_context or {})
    if unified.overview:
        context.update(
            {
                "unit_list": unified.overview.unit_list,
                "mixed_units": unified.overview.mixed_units,
                "weight_total": unified.overview.weight_total,
                "weight_source": unified.overview.weight_source,
                "participating_task_count": unified.overview.item_count,
                "text": "当前看板按“权重归一化统计”计算，所有图表和指标均基于当前筛选范围。",
            }
        )
    else:
        context.setdefault("unit_list", [])
        context.setdefault("mixed_units", False)
        context.setdefault("participating_task_count", 0)
        context.setdefault("text", "当前看板按“权重归一化统计”计算，所有图表和指标均基于当前筛选范围。")
    if unified.overview and unified.overview.batch_id:
        items = list_items(db, project.id, unified.overview.batch_id)
    else:
        # 聚合视图（同日期多 Sheet）没有单一 batch_id；诊断若用空列表会误报
        # 楼栋/楼层/权重不可用。此处用已经参与看板计算的响应内容修正能力判断。
        items = []
    diagnostics = build_item_diagnostics(items)
    if not items:
        diagnostics = _calculation_diagnostics_for_response(unified, context, diagnostics)
    dashboard_capabilities = _dashboard_capabilities_for_response(unified, diagnostics.get("dashboard_capabilities", {}))

    return DashboardV2Response(
        scope=DashboardV2Scope(
            project_id=project.id,
            view_mode=mode,
            scope_label=unified.filters.scope_label,
            message=unified.filters.message or ("当前筛选范围暂无数据。" if unified.overview and unified.overview.item_count == 0 else None),
            filters=unified.filters,
            options=unified.options,
        ),
        overview=unified.overview,
        discipline_cards=unified.by_discipline,
        building_cards=unified.by_building,
        floor_heatmap=unified.building_floor_matrix,
        building_elevation=unified.building_elevation,
        delay_distribution=unified.delay_distribution,
        delayed_items=unified.delayed_items,
        rectification_summary=unified.rectification_summary,
        calculation_context=context,
        calculation_diagnostics=diagnostics,
        dashboard_capabilities=dashboard_capabilities,
    )


def _calculation_diagnostics_for_response(unified, context: dict, fallback: dict) -> dict:
    diagnostics = dict(fallback or {})
    overview = unified.overview
    methods = [_method_to_dict(row) for row in (overview.available_calculation_methods if overview else [])]
    current_method = context.get("calculation_method") or (overview.calculation_method if overview else None)
    current_method_name = context.get("calculation_method_name") or (overview.calculation_method_name if overview else None)
    reason = context.get("recommendation_reason") or (overview.recommendation_reason if overview else None)

    if methods:
        if current_method:
            for method in methods:
                method["recommended"] = method.get("code") == current_method
        diagnostics["available_calculation_methods"] = methods
    if current_method:
        diagnostics["recommended_calculation_method"] = current_method
        diagnostics["recommended_calculation_method_name"] = current_method_name or _method_name_from_methods(current_method, methods)
    if reason:
        diagnostics["recommended_reason"] = reason
    if overview:
        diagnostics["unit_diagnostics"] = {
            "unit_field_exists": bool(overview.unit_list),
            "unit_list": overview.unit_list,
            "is_mixed": overview.mixed_units,
            "message": "当前数据包含多种单位，直接汇总工程量可能失真，建议使用权重统计或百分比平均。" if overview.mixed_units else None,
        }
        diagnostics["weight_diagnostics"] = {
            "weight_field_exists": bool(overview.weight_total),
            "weight_total": overview.weight_total,
            "valid_weight_task_count": overview.weight_count,
            "missing_weight_task_count": 0,
        }
        diagnostics["field_completeness_summary"] = {
            "quantity_field_complete_rate": _method_availability(methods, "quantity_percent"),
            "plan_date_complete_rate": 1.0 if overview.planned_percent is not None else 0.0,
            "actual_percent_complete_rate": 1.0 if overview.actual_percent is not None else 0.0,
        }
    return diagnostics


def _dashboard_capabilities_for_response(unified, fallback: dict) -> dict:
    capabilities = dict(fallback or {})
    has_discipline_data = bool(unified.by_discipline or unified.options.disciplines)
    has_building_data = bool(unified.by_building or unified.building_elevation or unified.building_floor_matrix)
    has_floor_data = bool(unified.by_floor or unified.building_floor_matrix or any(row.floors for row in unified.building_elevation))
    has_construction_unit_data = bool(unified.by_construction_unit or unified.options.construction_units)
    has_weight = bool((unified.calculation_context or {}).get("weight_total") or (unified.overview and unified.overview.weight_total))
    has_quantity = bool(
        (unified.calculation_context or {}).get("calculation_method") == "quantity_percent"
        or any(
            _method_value(row, "code") == "quantity_percent" and bool(_method_value(row, "available"))
            for row in (unified.overview.available_calculation_methods if unified.overview else [])
        )
    )
    has_percent = bool(unified.overview and unified.overview.actual_percent is not None)

    if has_discipline_data:
        capabilities["discipline_view"] = {"available": True, "reason": "已识别专业字段。"}
    if has_building_data:
        capabilities["building_view"] = {"available": True, "reason": "已识别楼栋字段。"}
    if has_floor_data:
        capabilities["floor_heatmap"] = {"available": True, "reason": "已识别楼层字段。"}
    if has_construction_unit_data:
        capabilities["construction_unit_filter"] = {"available": True, "reason": "已识别施工单位字段。"}
    if has_weight:
        capabilities["weighted_percent"] = {"available": True, "reason": "检测到权重字段。"}
    if has_quantity:
        capabilities["quantity_percent"] = {"available": True, "reason": "检测到完整工程量字段。"}
    if has_percent:
        capabilities["percent_average"] = {"available": True, "reason": "检测到实际完成率字段。"}
    capabilities.setdefault("overview", {"available": True, "reason": "总体视图可基于已导入任务展示。"})
    return capabilities


def _method_to_dict(row) -> dict:
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "model_dump"):
        return row.model_dump()
    if hasattr(row, "dict"):
        return row.dict()
    return {
        "code": getattr(row, "code", None),
        "name": getattr(row, "name", None),
        "available": getattr(row, "available", None),
        "reason": getattr(row, "reason", None),
        "recommended": getattr(row, "recommended", None),
    }


def _method_name_from_methods(code: str, methods: list[dict]) -> str | None:
    return next((str(method["name"]) for method in methods if method.get("code") == code and method.get("name")), None)


def _method_availability(methods: list[dict], code: str) -> float:
    return 1.0 if any(method.get("code") == code and bool(method.get("available")) for method in methods) else 0.0


def _method_value(row, key: str):
    if isinstance(row, dict):
        return row.get(key)
    return getattr(row, key, None)
