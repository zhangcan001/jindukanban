from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mapping_field import MappingField
from app.models.mapping_template import MappingTemplate
from app.models.project import Project
from app.schemas.mapping import FieldMapping, MatchedTemplate

CORE_FIELD_WEIGHTS = {
    "task_name": 3,
    "actual_percent": 3,
    "planned_percent": 3,
    "building": 2,
    "floor": 2,
    "discipline": 2,
    "construction_unit": 2,
    "total_quantity": 2,
    "cumulative_quantity": 2,
}


def compute_header_hash(columns: list[str]) -> str:
    """对列名序列计算可比较的指纹。

    用法：parse 时算出当前 Excel 的 header_hash，与历史 template 的 header_hash
    对比；命中即认为"列结构完全一致"，可直接套用 template 映射。

    规范化：剥离空白 / 标点 / 大小写差异（沿用列别名表的归一化），保留顺序——
    Excel 同样的字段如果顺序不同，照样会被认为是不同布局，因为按列位置导入
    时仍可能需要重新选择。
    """

    normalized = [_normalize(name) for name in columns if name and name.strip()]
    if not normalized:
        return ""
    payload = "".join(normalized).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def match_templates(
    db: Session,
    project_id: int,
    current_columns: list[str],
    min_score: float = 0.6,
    *,
    sheet_name: str | None = None,
) -> list[MatchedTemplate]:
    current_set = {_normalize(column) for column in current_columns if column.strip()}
    if not current_set:
        return []
    current_hash = compute_header_hash(current_columns)
    normalized_sheet = _normalize(sheet_name) if sheet_name else None

    project = db.get(Project, project_id)
    project_type = project.project_type if project else None
    scope_filter = (MappingTemplate.project_id == project_id) | (MappingTemplate.is_global.is_(True))
    if project_type:
        scope_filter = scope_filter | (MappingTemplate.project_type == project_type)

    statement = (
        select(MappingTemplate)
        .where(
            scope_filter & (MappingTemplate.is_active.is_(True))
        )
        .order_by(MappingTemplate.last_used_at.desc().nullslast(), MappingTemplate.id.desc())
    )
    matches: list[MatchedTemplate] = []
    for template in db.scalars(statement):
        fields = list(
            db.scalars(
                select(MappingField)
                .where(MappingField.template_id == template.id)
                .order_by(MappingField.sort_order.asc(), MappingField.id.asc())
            )
        )
        weighted_total = 0
        weighted_hit = 0
        for field in fields:
            if not field.excel_column_name.strip():
                continue
            weight = CORE_FIELD_WEIGHTS.get(field.system_field_name or "", 1)
            weighted_total += weight
            if _normalize(field.excel_column_name) in current_set:
                weighted_hit += weight * 2
                weighted_total += weight
            elif _alias_hit(field.system_field_name, current_set):
                weighted_hit += weight

        if weighted_total == 0:
            continue

        score = weighted_hit / weighted_total

        is_exact_match = bool(
            current_hash
            and template.header_hash
            and current_hash == template.header_hash
        )
        sheet_matches = bool(
            normalized_sheet
            and template.sheet_name
            and _normalize(template.sheet_name) == normalized_sheet
        )

        # 一键复用规则：header_hash 完全相同 → 直接 1.0 分；
        # header_hash 相同且 sheet_name 也匹配 → 标记 is_exact_match，前端展示"一键复用"
        if is_exact_match:
            score = 1.0
            match_reason = "列结构与历史模板完全一致" + ("，sheet 名同名" if sheet_matches else "")
        elif sheet_matches and score >= 0.5:
            # sheet 名命中但列略有变化，加 10% 分；不到 0.5 的不靠这个抢救
            score = min(1.0, score + 0.1)
            match_reason = f"sheet 名匹配 (+10% 加权)"
        else:
            match_reason = None

        if score >= min_score or is_exact_match:
            hit_fields = [field.excel_column_name for field in fields if _normalize(field.excel_column_name) in current_set]
            missing_fields = [field.excel_column_name for field in fields if field.excel_column_name and _normalize(field.excel_column_name) not in current_set]
            field_structure = _parse_structure(template.field_structure)
            matches.append(
                MatchedTemplate(
                    id=template.id,
                    name=template.name,
                    description=template.description,
                    match_score=round(score, 4),
                    hit_field_count=len(hit_fields),
                    missing_field_count=len(missing_fields),
                    possible_mismatch_fields=missing_fields[:8],
                    field_structure=field_structure,
                    fields=[
                        FieldMapping(
                            excel_column_name=field.excel_column_name,
                            recommended_field=field.system_field_name,
                            system_field_name=field.system_field_name,
                            field_type=field.field_type or "unknown",
                            is_dimension=field.is_dimension,
                            is_metric=field.is_metric,
                            is_required=field.is_required,
                            save_to_extra=field.save_to_extra,
                            sort_order=field.sort_order,
                        )
                        for field in fields
                    ],
                    is_exact_match=is_exact_match,
                    match_reason=match_reason,
                )
            )

    return sorted(matches, key=lambda item: (item.is_exact_match, item.match_score), reverse=True)


def mark_template_used(db: Session, template_id: int) -> None:
    template = db.get(MappingTemplate, template_id)
    if template is None:
        return
    template.last_used_at = datetime.now()
    template.use_count = (template.use_count or 0) + 1


def _normalize(value: str) -> str:
    return value.replace(" ", "").strip().lower()


def _parse_structure(value: str | None) -> dict | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _alias_hit(system_field: str | None, current_set: set[str]) -> bool:
    if not system_field:
        return False
    aliases = {
        "task_name": ["施工内容", "工作内容", "子项", "分项工程", "工序", "工序内容", "施工项", "任务名称"],
        "actual_percent": ["实际完成情况", "实际进度", "完成进度", "形象进度", "实际形象进度", "当前进度", "完成百分比", "完成比例"],
        "planned_percent": ["计划完成进度", "计划进度", "应完成率", "应完成进度", "目标进度", "计划完成率"],
        "building": ["楼栋", "单体", "楼号", "楼座"],
        "floor": ["楼层", "层", "所在楼层", "施工楼层"],
        "construction_unit": ["施工单位", "分包单位", "责任单位", "单位名称", "承包单位"],
    }
    return any(_normalize(alias) in current_set for alias in aliases.get(system_field, []))
