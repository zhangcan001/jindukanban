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
    items = list_items(db, project.id, unified.overview.batch_id) if unified.overview and unified.overview.batch_id else []
    diagnostics = build_item_diagnostics(items)

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
        dashboard_capabilities=diagnostics.get("dashboard_capabilities", {}),
    )
