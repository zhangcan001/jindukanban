from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha1
import json
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.baseline_plan import BaselinePlan
from app.models.calculation_profile import CalculationProfile
from app.models.import_batch import ImportBatch
from app.models.mapping_field import MappingField
from app.models.mapping_template import MappingTemplate
from app.models.progress_item import ProgressItem
from app.models.progress_task import ProgressTask
from app.models.project import Project
from app.models.raw_import_row import RawImportRow
from app.schemas.import_confirm import ImportConfirmRequest, ImportConfirmResponse
from app.schemas.validation import DataQualityScoreRead, ImportValidationIssueRead, summarize_issue_codes
from app.services.data_quality_service import calculate_data_quality_score
from app.services.import_validator import has_value, parse_number, parse_percent, should_skip_import, validate_import_rows
from app.services.progress_calculator import calculate_progress_fields
from app.services.field_diagnostics_service import build_mapping_diagnostics
from app.services.template_matcher import compute_header_hash, mark_template_used
from app.services.column_alias_service import record_aliases_bulk
from app.utils.date_utils import normalize_date

STANDARD_ITEM_FIELDS = {
    "wbs_code",
    "task_code",
    "task_name",
    "parent_task_name",
    "area",
    "construction_unit",
    "building",
    "floor",
    "discipline",
    "system_name",
    "unit",
    "total_quantity",
    "planned_quantity",
    "period_quantity",
    "cumulative_quantity",
    "actual_quantity",
    "remaining_quantity",
    "planned_percent",
    "imported_planned_percent",
    "actual_percent",
    "reported_percent",
    "time_planned_percent",
    "progress_deviation",
    "current_period_quantity",
    "current_period_percent",
    "planned_start_date",
    "planned_finish_date",
    "actual_start_date",
    "actual_finish_date",
    "weight",
    "value_amount",
    "status",
    "remark",
}

TASK_DIMENSION_FIELDS = {
    "area",
    "construction_unit",
    "building",
    "floor",
    "discipline",
    "system_name",
}

NUMBER_ITEM_FIELDS = {
    "total_quantity",
    "planned_quantity",
    "period_quantity",
    "cumulative_quantity",
    "actual_quantity",
    "remaining_quantity",
    "weight",
    "value_amount",
}

PERCENT_ITEM_FIELDS = {
    "planned_percent",
    "imported_planned_percent",
    "actual_percent",
    "reported_percent",
    "time_planned_percent",
    "progress_deviation",
    "current_period_percent",
}

DATE_ITEM_FIELDS = {
    "planned_start_date",
    "planned_finish_date",
    "actual_start_date",
    "actual_finish_date",
}


@dataclass
class ImportCounters:
    imported_count: int = 0
    skipped_count: int = 0
    task_created_count: int = 0
    task_matched_count: int = 0
    raw_row_count: int = 0


def confirm_import_batch(
    db: Session,
    batch: ImportBatch,
    raw_rows: list[dict[str, Any]],
    payload: ImportConfirmRequest,
) -> ImportConfirmResponse:
    issues, normalized_rows = validate_import_rows(raw_rows, payload.field_mappings)
    warning_count = sum(1 for issue in issues if issue.level == "warning")
    error_count = sum(1 for issue in issues if issue.level == "error")
    blocking_errors = [issue for issue in issues if issue.level == "error"]
    row_error_indexes = {issue.row_index for issue in issues if issue.level == "error" and issue.row_index is not None}
    importable_rows = [row for row in normalized_rows if not should_skip_import(row)]
    data_quality = calculate_data_quality_score(db, batch.project_id, importable_rows, payload.field_mappings, issues)

    if blocking_errors:
        _update_batch_validation(batch, warning_count, error_count, data_quality)
        return ImportConfirmResponse(
            valid=False,
            status=batch.status,
            imported_count=0,
            skipped_count=len(raw_rows),
            task_created_count=0,
            task_matched_count=0,
            raw_row_count=0,
            template_id=None,
            warning_count=warning_count,
            error_count=error_count,
            data_quality=data_quality,
            issues=issues,
            issue_code_counts=summarize_issue_codes(issues),
        )

    if not importable_rows:
        _update_batch_validation(batch, warning_count, error_count, data_quality)
        batch.skipped_count = len(raw_rows)
        no_importable_issues = [
            *issues,
            ImportValidationIssueRead(
                row_index=None,
                column_name=None,
                level="warning",
                code="NO_IMPORTABLE_ROWS",
                message="该 Sheet 可能不是进度明细表，未生成有效进度数据，不建议发布。",
            ),
        ]
        return ImportConfirmResponse(
            valid=False,
            status=batch.status,
            imported_count=0,
            skipped_count=len(raw_rows),
            task_created_count=0,
            task_matched_count=0,
            raw_row_count=0,
            template_id=None,
            warning_count=warning_count,
            error_count=error_count,
            data_quality=data_quality,
            issues=no_importable_issues,
            issue_code_counts=summarize_issue_codes(no_importable_issues),
        )

    _apply_import_strategy(db, batch, payload.import_strategy)
    if payload.import_strategy == "overwrite_current":
        _clear_current_batch_rows(db, batch.id)

    calculation_profile = _resolve_calculation_profile(db, batch.project_id, payload.calculation_profile_id)
    baseline_plan = _resolve_baseline_plan(db, batch.project_id, payload.baseline_plan_id)
    calculation_profile_id = calculation_profile.id if calculation_profile else None
    baseline_plan_id = baseline_plan.id if baseline_plan else None

    selected_template_id = payload.mapping_template_id or batch.mapping_template_id
    if payload.save_as_template:
        template_id = _save_mapping_template(db, batch, payload)
    elif selected_template_id:
        template_id = selected_template_id
    else:
        template_id = _auto_save_mapping_template(db, batch, payload)
    if selected_template_id:
        mark_template_used(db, selected_template_id)
    record_aliases_bulk(
        db,
        project_id=batch.project_id,
        mappings=[
            (mapping.excel_column_name, mapping.system_field_name, mapping.field_type)
            for mapping in payload.field_mappings
        ],
    )
    counters = ImportCounters()
    seen_identity_keys: set[str] = set()
    duplicate_issues: list[ImportValidationIssueRead] = []
    for row_index, (raw_row, normalized_row) in enumerate(zip(raw_rows, normalized_rows, strict=False), start=1):
        db.add(
            RawImportRow(
                batch_id=batch.id,
                row_index=row_index,
                raw_data=json.dumps(raw_row, ensure_ascii=False, default=str),
            )
        )
        counters.raw_row_count += 1

        if should_skip_import(normalized_row) or row_index in row_error_indexes:
            counters.skipped_count += 1
            continue

        task, created = _match_or_create_task(db, batch.project_id, normalized_row, row_index)
        counters.task_created_count += 1 if created else 0
        counters.task_matched_count += 0 if created else 1
        # 同一批次里同一 identity_key 已经写过一次就跳过——避免 Excel 里重复行造成统计扭曲。
        # 空 identity_key 是兜底,身份本就不可靠,不参与去重。
        identity_key_for_row = task.identity_key or ""
        if identity_key_for_row and identity_key_for_row in seen_identity_keys:
            counters.skipped_count += 1
            duplicate_issues.append(
                ImportValidationIssueRead(
                    row_index=row_index,
                    column_name=None,
                    level="warning",
                    code="DUPLICATE_IDENTITY_KEY",
                    message=f"第 {row_index} 行与本批次中已处理的任务身份重复（identity_key={identity_key_for_row}），已跳过避免重复写入。",
                )
            )
            continue
        if identity_key_for_row:
            seen_identity_keys.add(identity_key_for_row)
        db.add(_build_progress_item(db, batch, task, normalized_row, raw_row, payload, calculation_profile, baseline_plan_id))
        counters.imported_count += 1

    if duplicate_issues:
        issues = [*issues, *duplicate_issues]
        warning_count += len(duplicate_issues)

    batch.imported_count = counters.imported_count
    batch.skipped_count = counters.skipped_count
    batch.warning_count = warning_count
    batch.error_count = error_count
    batch.data_quality_score = data_quality.data_quality_score
    batch.field_completeness = data_quality.field_completeness
    batch.task_match_rate = data_quality.task_match_rate
    batch.valid_row_rate = data_quality.valid_row_rate
    batch.plan_field_completeness = data_quality.plan_field_completeness
    batch.unit_consistency = data_quality.unit_consistency
    batch.mapping_template_id = template_id
    batch.calculation_profile_id = calculation_profile_id
    batch.baseline_plan_id = baseline_plan_id
    batch.import_strategy = payload.import_strategy
    batch.is_active = True
    batch.status = "imported"

    db.add(
        AuditLog(
            project_id=batch.project_id,
            entity_type="import_batch",
            entity_id=batch.id,
            action="confirm_import",
            detail=json.dumps(
                {
                    "import_strategy": payload.import_strategy,
                    "imported_count": counters.imported_count,
                    "task_created_count": counters.task_created_count,
                    "task_matched_count": counters.task_matched_count,
                    "template_id": template_id,
                    "calculation_profile_id": calculation_profile_id,
                    "baseline_plan_id": baseline_plan_id,
                },
                ensure_ascii=False,
            ),
            created_by="system",
        )
    )

    return ImportConfirmResponse(
        valid=True,
        status="imported",
        imported_count=counters.imported_count,
        skipped_count=counters.skipped_count,
        task_created_count=counters.task_created_count,
        task_matched_count=counters.task_matched_count,
        raw_row_count=counters.raw_row_count,
        template_id=template_id,
        warning_count=warning_count,
        error_count=error_count,
        data_quality=data_quality,
        issues=issues,
        issue_code_counts=summarize_issue_codes(issues),
    )


def _update_batch_validation(
    batch: ImportBatch,
    warning_count: int,
    error_count: int,
    data_quality: DataQualityScoreRead,
) -> None:
    batch.warning_count = warning_count
    batch.error_count = error_count
    batch.data_quality_score = data_quality.data_quality_score
    batch.field_completeness = data_quality.field_completeness
    batch.task_match_rate = data_quality.task_match_rate
    batch.valid_row_rate = data_quality.valid_row_rate
    batch.plan_field_completeness = data_quality.plan_field_completeness
    batch.unit_consistency = data_quality.unit_consistency
    batch.status = "parsed"


def _apply_import_strategy(db: Session, batch: ImportBatch, strategy: str) -> None:
    if strategy == "replace_same_date" and batch.data_date is not None:
        frozen_batch = db.scalar(
            select(ImportBatch).where(
                ImportBatch.project_id == batch.project_id,
                ImportBatch.data_date == batch.data_date,
                ImportBatch.sheet_name == batch.sheet_name,
                ImportBatch.id != batch.id,
                ImportBatch.is_active.is_(True),
                ImportBatch.is_frozen.is_(True),
            )
        )
        if frozen_batch is not None:
            raise ValueError("同日期同 Sheet 已存在冻结批次，请先取消冻结后再替换。")
        db.execute(
            update(ImportBatch)
            .where(
                ImportBatch.project_id == batch.project_id,
                ImportBatch.data_date == batch.data_date,
                ImportBatch.sheet_name == batch.sheet_name,
                ImportBatch.id != batch.id,
                ImportBatch.is_active.is_(True),
                ImportBatch.is_frozen.is_(False),
            )
            .values(is_active=False)
        )


def _clear_current_batch_rows(db: Session, batch_id: int) -> None:
    db.execute(delete(ProgressItem).where(ProgressItem.batch_id == batch_id))
    db.execute(delete(RawImportRow).where(RawImportRow.batch_id == batch_id))


def _resolve_calculation_profile(
    db: Session,
    project_id: int,
    requested_profile_id: int | None,
) -> CalculationProfile | None:
    if requested_profile_id is not None:
        profile = db.get(CalculationProfile, requested_profile_id)
        if profile is not None and profile.project_id == project_id:
            return profile

    project = db.get(Project, project_id)
    if project and project.default_calculation_profile_id:
        profile = db.get(CalculationProfile, project.default_calculation_profile_id)
        if profile is not None and profile.project_id == project_id:
            return profile

    return db.execute(
        select(CalculationProfile).where(CalculationProfile.project_id == project_id).order_by(CalculationProfile.is_default.desc(), CalculationProfile.id)
    ).scalars().first()


def _resolve_baseline_plan(db: Session, project_id: int, requested_baseline_id: int | None) -> BaselinePlan | None:
    if requested_baseline_id is not None:
        baseline = db.get(BaselinePlan, requested_baseline_id)
        if baseline is not None and baseline.project_id == project_id and baseline.is_active:
            return baseline

    project = db.get(Project, project_id)
    if project and project.default_baseline_plan_id:
        baseline = db.get(BaselinePlan, project.default_baseline_plan_id)
        if baseline is not None and baseline.project_id == project_id and baseline.is_active:
            return baseline

    return db.execute(
        select(BaselinePlan)
        .where(BaselinePlan.project_id == project_id, BaselinePlan.is_active.is_(True))
        .order_by(BaselinePlan.is_default.desc(), BaselinePlan.id)
    ).scalars().first()


def _save_mapping_template(db: Session, batch: ImportBatch, payload: ImportConfirmRequest) -> int:
    project_id = batch.project_id
    project = db.get(Project, project_id)
    header_hash = compute_header_hash([mapping.excel_column_name for mapping in payload.field_mappings])
    diagnostics = build_mapping_diagnostics(_template_batch(project_id, batch, payload), payload.field_mappings, [])
    template = MappingTemplate(
        project_id=project_id,
        name=payload.template_name or f"导入模板 {datetime.now().strftime('%Y%m%d%H%M%S')}",
        description="由正式导入保存",
        project_type=project.project_type if project else None,
        sheet_name=payload.sheet_name or batch.sheet_name,
        header_hash=header_hash,
        field_structure=_mapping_template_structure(batch, payload, diagnostics),
        is_global=False,
        is_active=True,
        last_used_at=datetime.now(),
        use_count=1,
    )
    db.add(template)
    db.flush()
    for mapping in payload.field_mappings:
        db.add(
            MappingField(
                template_id=template.id,
                excel_column_name=mapping.excel_column_name,
                system_field_name=mapping.system_field_name,
                field_type=mapping.field_type,
                is_dimension=mapping.is_dimension,
                is_metric=mapping.is_metric,
                is_required=mapping.is_required,
                save_to_extra=mapping.save_to_extra,
                sort_order=mapping.sort_order,
            )
        )
    return template.id


def _auto_save_mapping_template(db: Session, batch: ImportBatch, payload: ImportConfirmRequest) -> int | None:
    header_hash = compute_header_hash([mapping.excel_column_name for mapping in payload.field_mappings])
    if not header_hash:
        return None

    project = db.get(Project, batch.project_id)
    sheet_name = payload.sheet_name or batch.sheet_name
    diagnostics = build_mapping_diagnostics(_template_batch(batch.project_id, batch, payload), payload.field_mappings, [])
    existing = db.scalars(
        select(MappingTemplate)
        .where(
            MappingTemplate.project_id == batch.project_id,
            MappingTemplate.header_hash == header_hash,
            MappingTemplate.is_active.is_(True),
        )
        .order_by(MappingTemplate.last_used_at.desc().nullslast(), MappingTemplate.id.desc())
    ).first()

    if existing is not None:
        existing.sheet_name = existing.sheet_name or sheet_name
        existing.field_structure = _mapping_template_structure(batch, payload, diagnostics)
        existing.project_type = existing.project_type or (project.project_type if project else None)
        _replace_mapping_fields(db, existing.id, payload)
        mark_template_used(db, existing.id)
        return existing.id

    template = MappingTemplate(
        project_id=batch.project_id,
        name=_auto_template_name(batch),
        description="导入成功后自动保存",
        project_type=project.project_type if project else None,
        sheet_name=sheet_name,
        header_hash=header_hash,
        field_structure=_mapping_template_structure(batch, payload, diagnostics),
        is_global=False,
        is_active=True,
        last_used_at=datetime.now(),
        use_count=1,
    )
    db.add(template)
    db.flush()
    _add_mapping_fields(db, template.id, payload)
    return template.id


def _mapping_template_structure(batch: ImportBatch, payload: ImportConfirmRequest, diagnostics: dict[str, Any]) -> str:
    return json.dumps(
        {
            "sheet_name": payload.sheet_name or batch.sheet_name,
            "original_columns": [mapping.excel_column_name for mapping in payload.field_mappings],
            "system_fields": [mapping.system_field_name for mapping in payload.field_mappings if mapping.system_field_name],
            "columns": [
                {
                    "excel_column_name": mapping.excel_column_name,
                    "system_field_name": mapping.system_field_name,
                    "field_type": mapping.field_type,
                    "is_dimension": mapping.is_dimension,
                    "is_metric": mapping.is_metric,
                    "is_required": mapping.is_required,
                    "save_to_extra": mapping.save_to_extra,
                    "sort_order": mapping.sort_order,
                }
                for mapping in payload.field_mappings
            ],
            "header_row_index": batch.header_row_index,
            "data_start_row_index": batch.data_start_row_index,
            "recommended_calculation_method": diagnostics.get("recommended_calculation_method"),
            "recommended_calculation_method_name": diagnostics.get("recommended_calculation_method_name"),
            "available_calculation_methods": diagnostics.get("available_calculation_methods"),
            "field_completeness_summary": diagnostics.get("field_completeness_summary"),
            "field_mapping_quality": diagnostics.get("field_mapping_quality"),
        },
        ensure_ascii=False,
    )


def _add_mapping_fields(db: Session, template_id: int, payload: ImportConfirmRequest) -> None:
    for mapping in payload.field_mappings:
        db.add(
            MappingField(
                template_id=template_id,
                excel_column_name=mapping.excel_column_name,
                system_field_name=mapping.system_field_name,
                field_type=mapping.field_type,
                is_dimension=mapping.is_dimension,
                is_metric=mapping.is_metric,
                is_required=mapping.is_required,
                save_to_extra=mapping.save_to_extra,
                sort_order=mapping.sort_order,
            )
        )


def _replace_mapping_fields(db: Session, template_id: int, payload: ImportConfirmRequest) -> None:
    db.execute(delete(MappingField).where(MappingField.template_id == template_id))
    _add_mapping_fields(db, template_id, payload)


def _auto_template_name(batch: ImportBatch) -> str:
    sheet = batch.sheet_name or "默认Sheet"
    return f"{sheet} 自动字段模板"


def _template_batch(project_id: int, batch: ImportBatch, payload: ImportConfirmRequest) -> ImportBatch:
    return ImportBatch(
        project_id=project_id,
        file_name="",
        sheet_name=payload.sheet_name or batch.sheet_name,
        header_row_index=batch.header_row_index,
        data_start_row_index=batch.data_start_row_index,
        multi_header=batch.multi_header,
        header_end_row_index=batch.header_end_row_index,
    )


def _match_or_create_task(
    db: Session,
    project_id: int,
    row: dict[str, Any],
    row_index: int,
) -> tuple[ProgressTask, bool]:
    identity_key = _identity_key(row)
    normalized_name = _normalize(row.get("task_name"))
    task = _find_task(db, project_id, row, identity_key, normalized_name)
    if task is not None:
        _refresh_task_dimensions(task, row)
        return task, False

    parent_task = _resolve_parent_task(db, project_id, row, row_index)
    task = ProgressTask(
        project_id=project_id,
        wbs_code=_text(row.get("wbs_code")),
        task_code=_text(row.get("task_code")),
        task_name=_text(row.get("task_name")),
        normalized_task_name=normalized_name,
        parent_task_id=parent_task.id if parent_task else None,
        parent_task_name=_text(row.get("parent_task_name")),
        task_level=_task_level(row),
        sort_order=row_index,
        area=_text(row.get("area")),
        building=_text(row.get("building")),
        floor=_text(row.get("floor")),
        discipline=_text(row.get("discipline")),
        system_name=_text(row.get("system_name")),
        identity_key=identity_key,
        is_active=True,
    )
    db.add(task)
    db.flush()
    return task, True


def _find_task(
    db: Session,
    project_id: int,
    row: dict[str, Any],
    identity_key: str,
    normalized_name: str,
) -> ProgressTask | None:
    task_code = _text(row.get("task_code"))
    if task_code:
        task = db.execute(
            select(ProgressTask).where(
                ProgressTask.project_id == project_id,
                ProgressTask.is_active.is_(True),
                ProgressTask.task_code == task_code,
            )
        ).scalars().first()
        if task:
            return task

    wbs_code = _text(row.get("wbs_code"))
    task_name = _text(row.get("task_name"))
    if wbs_code and task_name:
        task = db.execute(
            select(ProgressTask).where(
                ProgressTask.project_id == project_id,
                ProgressTask.is_active.is_(True),
                ProgressTask.wbs_code == wbs_code,
                ProgressTask.task_name == task_name,
            )
        ).scalars().first()
        if task:
            return task

    if identity_key:
        task = db.execute(
            select(ProgressTask).where(
                ProgressTask.project_id == project_id,
                ProgressTask.is_active.is_(True),
                ProgressTask.identity_key == identity_key,
            )
        ).scalars().first()
        if task:
            return task

    return db.execute(
        select(ProgressTask).where(
            ProgressTask.project_id == project_id,
            ProgressTask.is_active.is_(True),
            ProgressTask.normalized_task_name == normalized_name,
            ProgressTask.area == _text(row.get("area")),
            ProgressTask.building == _text(row.get("building")),
            ProgressTask.floor == _text(row.get("floor")),
            ProgressTask.discipline == _text(row.get("discipline")),
            ProgressTask.system_name == _text(row.get("system_name")),
        )
    ).scalars().first()


def _resolve_parent_task(db: Session, project_id: int, row: dict[str, Any], row_index: int) -> ProgressTask | None:
    parent_task_id = parse_number(row.get("parent_task_id"))
    if parent_task_id is not None:
        parent = db.get(ProgressTask, int(parent_task_id))
        if parent and parent.project_id == project_id and parent.is_active:
            return parent

    parent_name = _text(row.get("parent_task_name"))
    if not parent_name:
        return None

    normalized_parent_name = _normalize(parent_name)
    parent = db.execute(
        select(ProgressTask).where(
            ProgressTask.project_id == project_id,
            ProgressTask.is_active.is_(True),
            ProgressTask.normalized_task_name == normalized_parent_name,
        )
    ).scalars().first()
    if parent:
        return parent

    parent = ProgressTask(
        project_id=project_id,
        task_name=parent_name,
        normalized_task_name=normalized_parent_name,
        task_level=max(_task_level(row) - 1, 1),
        sort_order=max(row_index - 1, 0),
        identity_key=_hash_key([parent_name]),
        is_active=True,
    )
    db.add(parent)
    db.flush()
    return parent


def _refresh_task_dimensions(task: ProgressTask, row: dict[str, Any]) -> None:
    for field in TASK_DIMENSION_FIELDS:
        value = _text(row.get(field))
        if value and not getattr(task, field):
            setattr(task, field, value)
    if _text(row.get("parent_task_name")) and not task.parent_task_name:
        task.parent_task_name = _text(row.get("parent_task_name"))


def _build_progress_item(
    db: Session,
    batch: ImportBatch,
    task: ProgressTask,
    row: dict[str, Any],
    raw_row: dict[str, Any],
    payload: ImportConfirmRequest,
    calculation_profile: CalculationProfile | None,
    baseline_plan_id: int | None,
) -> ProgressItem:
    values = {field: _coerce_item_value(field, row.get(field)) for field in STANDARD_ITEM_FIELDS}
    previous_item = _find_previous_progress_item(db, batch, task.id)
    values = calculate_progress_fields(values, calculation_profile, batch.data_date, previous_item)
    return ProgressItem(
        project_id=batch.project_id,
        batch_id=batch.id,
        task_id=task.id,
        baseline_plan_id=baseline_plan_id,
        identity_key=task.identity_key,
        extra_fields=json.dumps(_extra_fields(raw_row, payload), ensure_ascii=False, default=str) or None,
        **values,
    )


def _find_previous_progress_item(db: Session, batch: ImportBatch, task_id: int) -> ProgressItem | None:
    previous_batch_ids = (
        select(ImportBatch.id)
        .where(
            ImportBatch.project_id == batch.project_id,
            ImportBatch.id != batch.id,
            ImportBatch.is_active.is_(True),
            ImportBatch.status.in_(["imported", "published"]),
        )
        .order_by(ImportBatch.data_date.desc().nullslast(), ImportBatch.id.desc())
    )
    return db.execute(
        select(ProgressItem)
        .where(ProgressItem.task_id == task_id, ProgressItem.batch_id.in_(previous_batch_ids))
        .order_by(ProgressItem.batch_id.desc())
    ).scalars().first()


def _extra_fields(raw_row: dict[str, Any], payload: ImportConfirmRequest) -> dict[str, Any]:
    mapping_by_column = {mapping.excel_column_name: mapping for mapping in payload.field_mappings}
    extra: dict[str, Any] = {}
    for key, value in raw_row.items():
        if not has_value(value):
            continue
        mapping = mapping_by_column.get(key)
        if mapping is None:
            extra[key] = value
        elif mapping.save_to_extra:
            extra[key] = value
    return extra


def _coerce_item_value(field: str, value: Any) -> Any:
    if field == "weight":
        return _parse_weight(value)
    if field in NUMBER_ITEM_FIELDS:
        return parse_number(value)
    if field in PERCENT_ITEM_FIELDS:
        return parse_percent(value)
    if field in DATE_ITEM_FIELDS:
        return _parse_date(value)
    return _text(value)


def _parse_weight(value: Any) -> float | None:
    number = parse_number(value)
    if number is None:
        return None
    if number > 1:
        return round(number / 100, 6)
    return round(number, 6)


def _parse_date(value: Any) -> date | None:
    return normalize_date(value)


def _identity_key(row: dict[str, Any]) -> str:
    explicit_key = _text(row.get("identity_key"))
    if explicit_key:
        return explicit_key
    task_code = _text(row.get("task_code"))
    if task_code:
        return _normalize(task_code)
    return _hash_key(
        [
            row.get("task_name"),
            row.get("area"),
            row.get("building"),
            row.get("floor"),
            row.get("discipline"),
            row.get("system_name"),
        ]
    )


def _hash_key(values: list[Any]) -> str:
    normalized = "|".join(_normalize(value) for value in values if has_value(value))
    return sha1(normalized.encode("utf-8")).hexdigest() if normalized else ""


def _task_level(row: dict[str, Any]) -> int:
    level = parse_number(row.get("task_level"))
    if level is not None and level >= 1:
        return int(level)
    wbs_code = _text(row.get("wbs_code"))
    if not wbs_code:
        return 1
    return max(1, len([part for part in wbs_code.replace("-", ".").split(".") if part.strip()]))


def _normalize(value: Any) -> str:
    if not has_value(value):
        return ""
    return "".join(str(value).strip().lower().split())


def _text(value: Any) -> str | None:
    if not has_value(value):
        return None
    return str(value).strip()
