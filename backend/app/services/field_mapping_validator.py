from __future__ import annotations

from app.schemas.mapping import FieldMapping, MappingValidationIssue


def validate_field_mappings(field_mappings: list[FieldMapping]) -> list[MappingValidationIssue]:
    issues: list[MappingValidationIssue] = []
    seen: dict[str, str] = {}

    for mapping in field_mappings:
        system_field = (mapping.system_field_name or "").strip()
        excel_column = mapping.excel_column_name.strip()
        if not system_field:
            continue
        if system_field in seen:
            issues.append(
                MappingValidationIssue(
                    level="error",
                    code="duplicate_system_field",
                    message=f"字段 {system_field} 已被“{seen[system_field]}”映射，不能再映射“{excel_column}”。",
                    excel_column_name=excel_column,
                    system_field_name=system_field,
                )
            )
        else:
            seen[system_field] = excel_column

    for mapping in field_mappings:
        if mapping.is_required and not (mapping.system_field_name or "").strip():
            issues.append(
                MappingValidationIssue(
                    level="error",
                    code="required_mapping_missing",
                    message=f"字段“{mapping.excel_column_name}”被标记为必填，但未选择系统字段。",
                    excel_column_name=mapping.excel_column_name,
                )
            )

    return issues

