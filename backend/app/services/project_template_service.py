from __future__ import annotations

from datetime import datetime
import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.calculation_profile import CalculationProfile
from app.models.project import Project
from app.models.project_template import ProjectTemplate
from app.models.warning_rule import WarningRule


BUILTIN_PROJECT_TEMPLATES = [
    {
        "code": "mep-installation",
        "name": "机电安装项目模板",
        "description": "适用于机电安装周进度导入、楼层统计和滞后项跟踪。",
        "project_type": "机电安装",
        "dashboard_dimensions": ["discipline", "building", "floor", "system_name"],
        "profile": {"name": "机电安装默认统计口径", "overall_algorithm": "avg_percent", "group_algorithm": "avg_percent"},
    },
    {
        "code": "fire-protection",
        "name": "消防工程项目模板",
        "description": "适用于消防工程按系统、楼栋、楼层跟踪整改。",
        "project_type": "消防工程",
        "dashboard_dimensions": ["system_name", "building", "floor", "discipline"],
        "profile": {"name": "消防工程默认统计口径", "overall_algorithm": "avg_percent", "group_algorithm": "avg_percent"},
    },
    {
        "code": "intelligent",
        "name": "智能化工程项目模板",
        "description": "适用于智能化工程按系统和区域跟踪进度。",
        "project_type": "智能化工程",
        "dashboard_dimensions": ["system_name", "area", "building", "floor"],
        "profile": {"name": "智能化工程默认统计口径", "overall_algorithm": "avg_percent", "group_algorithm": "avg_percent"},
    },
    {
        "code": "general-progress",
        "name": "通用进度项目模板",
        "description": "适用于常规工程进度导入、看板分析和报表导出。",
        "project_type": "通用工程",
        "dashboard_dimensions": ["discipline", "building", "floor"],
        "profile": {"name": "通用默认统计口径", "overall_algorithm": "avg_percent", "group_algorithm": "avg_percent"},
    },
]

DEFAULT_WARNING_RULES = [
    {"name": "严重滞后", "rule_type": "severe_delay", "level": "error", "threshold_value": -10, "is_enabled": True},
    {"name": "连续滞后", "rule_type": "continuous_delay", "level": "warning", "threshold_value": 0, "is_enabled": True},
    {"name": "本期完成量为 0", "rule_type": "zero_period_quantity", "level": "warning", "threshold_value": 0, "is_enabled": True},
]

DEFAULT_FIELD_ALIASES = {
    "task_name": ["施工内容", "工作内容", "子项", "分项工程", "工序", "工序内容", "施工项", "任务名称"],
    "actual_percent": ["实际完成情况", "实际进度", "完成进度", "形象进度", "实际形象进度", "当前进度", "完成百分比", "完成比例"],
    "planned_percent": ["计划完成进度", "计划进度", "应完成率", "应完成进度", "目标进度", "计划完成率"],
    "building": ["楼栋", "单体", "楼号", "楼座"],
    "floor": ["楼层", "层", "所在楼层", "施工楼层"],
    "extra_fields": ["责任人", "负责人", "责任工程师", "施工单位", "分包单位", "班组", "施工班组"],
}

DEFAULT_REPORT_CONFIG = {
    "dashboard_excel": True,
    "weekly_word": True,
    "delay_rectification_excel": True,
    "include_advanced_chart_analysis": True,
    "weekly_delayed_item_limit": 30,
    "weekly_matrix_summary_limit": 10,
    "show_data_quality_section": True,
    "show_rectification_summary": True,
    "default_export_format": "xlsx",
    "file_name_include_project_name": True,
    "file_name_include_data_date": True,
}


def ensure_builtin_project_templates(db: Session) -> None:
    existing_codes = set(db.scalars(select(ProjectTemplate.code)).all())
    for item in BUILTIN_PROJECT_TEMPLATES:
        if item["code"] in existing_codes:
            continue
        dashboard_config = {"dimensions": item["dashboard_dimensions"], "default_view": "dashboard"}
        template = ProjectTemplate(
            code=item["code"],
            name=item["name"],
            description=item["description"],
            project_type=item["project_type"],
            is_builtin=True,
            is_active=True,
            default_calculation_profile=_json(item["profile"]),
            default_warning_rules=_json(DEFAULT_WARNING_RULES),
            default_field_aliases=_json(DEFAULT_FIELD_ALIASES),
            default_dashboard_config=_json(dashboard_config),
            default_report_config=_json(DEFAULT_REPORT_CONFIG),
        )
        db.add(template)
    db.commit()


def apply_project_template(db: Session, project: Project, template: ProjectTemplate) -> None:
    project.template_id = template.id
    if template.project_type and not project.project_type:
        project.project_type = template.project_type
    project.dashboard_config = template.default_dashboard_config
    project.report_config = template.default_report_config

    profile_data = _loads(template.default_calculation_profile)
    profile = CalculationProfile(
        project_id=project.id,
        name=profile_data.get("name") or f"{template.name}统计口径",
        overall_algorithm=profile_data.get("overall_algorithm") or "avg_percent",
        group_algorithm=profile_data.get("group_algorithm") or "avg_percent",
        percent_source=profile_data.get("percent_source") or "provided_percent_first",
        use_weight=bool(profile_data.get("use_weight", False)),
        weight_field=profile_data.get("weight_field"),
        use_value_amount=bool(profile_data.get("use_value_amount", False)),
        value_field=profile_data.get("value_field"),
        allow_mixed_unit_sum=bool(profile_data.get("allow_mixed_unit_sum", False)),
        enable_date_plan_calculation=bool(profile_data.get("enable_date_plan_calculation", True)),
        is_default=True,
    )
    db.add(profile)
    db.flush()
    project.default_calculation_profile_id = profile.id

    for rule_data in _loads_list(template.default_warning_rules):
        db.add(
            WarningRule(
                project_id=project.id,
                name=rule_data.get("name") or "模板预警规则",
                rule_type=rule_data.get("rule_type") or "severe_delay",
                level=rule_data.get("level") or "warning",
                threshold_value=rule_data.get("threshold_value"),
                is_enabled=bool(rule_data.get("is_enabled", True)),
            )
        )


def copy_project_template(db: Session, template: ProjectTemplate) -> ProjectTemplate:
    copied = ProjectTemplate(
        name=f"{template.name} 副本",
        code=f"{template.code}-copy-{uuid4().hex[:8]}",
        description=template.description,
        project_type=template.project_type,
        is_builtin=False,
        is_active=True,
        default_calculation_profile=template.default_calculation_profile,
        default_warning_rules=template.default_warning_rules,
        default_field_aliases=template.default_field_aliases,
        default_dashboard_config=template.default_dashboard_config,
        default_report_config=template.default_report_config,
    )
    db.add(copied)
    db.flush()
    return copied


def touch_mapping_template(template) -> None:
    template.last_used_at = datetime.now()
    template.use_count = (template.use_count or 0) + 1


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads(value: str | None) -> dict:
    if not value:
        return {}
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else {}


def _loads_list(value: str | None) -> list[dict]:
    if not value:
        return []
    parsed = json.loads(value)
    return parsed if isinstance(parsed, list) else []
