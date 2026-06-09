from pathlib import Path
from datetime import date, datetime
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import delete, update
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.database import get_db
from app.config import get_settings
from app.models.audit_log import AuditLog
from app.models.import_batch import ImportBatch
from app.models.import_validation_issue import ImportValidationIssue
from app.models.maintenance_log import MaintenanceLog
from app.models.project import Project
from app.schemas.import_confirm import (
    ImportConfirmRequest,
    ImportConfirmResponse,
    MultiSheetConfirmBatchResult,
    MultiSheetConfirmRequest,
    MultiSheetConfirmResponse,
)
from app.schemas.import_batch import (
    ImportBatchRead,
    ImportParseRequest,
    ImportParseResponse,
    ImportUploadResponse,
    MultiSheetParseRequest,
    MultiSheetParseResponse,
    MultiSheetParseResult,
)
from app.schemas.import_publish import ImportPublishResponse, MultiSheetPublishResponse, MultiSheetPublishResult
from app.schemas.mapping import MappingValidationRequest, MappingValidationResponse
from app.schemas.validation import (
    ImportValidationRequest,
    ImportValidationResponse,
    MultiSheetValidationRequest,
    MultiSheetValidationResponse,
    MultiSheetValidationResult,
    summarize_issue_codes,
)
from app.services.field_mapping_validator import validate_field_mappings
from app.services.field_diagnostics_service import build_item_diagnostics, build_mapping_diagnostics, build_parse_field_diagnostics
from app.services.template_matcher import match_templates
from app.services.column_alias_service import enrich_columns_with_aliases
from app.models.progress_item import ProgressItem
from app.schemas.mapping import FieldMapping

router = APIRouter(tags=["imports"])

UPLOAD_DIR = Path(get_settings().upload_dir)
SUPPORTED_SUFFIXES = {".xlsx", ".csv"}


def _excel_parser():
    from app.services import excel_parser

    return excel_parser


def _import_validator():
    from app.services import import_validator

    return import_validator


class ExcelParseError(ValueError):
    def __init__(self, message: str, code: str = "EXCEL_PARSE_ERROR") -> None:
        super().__init__(message)
        self.code = code


def _raise_excel_error(exc: Exception) -> None:
    raise ExcelParseError(str(exc), getattr(exc, "code", "EXCEL_PARSE_ERROR")) from exc


def get_sheet_names(file_path: str):
    parser = _excel_parser()
    try:
        return parser.get_sheet_names(file_path)
    except parser.ExcelParseError as exc:
        _raise_excel_error(exc)


def _read_raw(file_path: str, sheet_name: str):
    parser = _excel_parser()
    try:
        return parser._read_raw(file_path, sheet_name)
    except parser.ExcelParseError as exc:
        _raise_excel_error(exc)


def resolve_header_rows(file_path: str, sheet_name: str, header_row_index: int | None, data_start_row_index: int | None):
    parser = _excel_parser()
    try:
        return parser.resolve_header_rows(file_path, sheet_name, header_row_index, data_start_row_index)
    except parser.ExcelParseError as exc:
        _raise_excel_error(exc)


def infer_multi_header_end(raw, header_row_index: int):
    return _excel_parser().infer_multi_header_end(raw, header_row_index)


def recommend_header_rows(raw):
    return _excel_parser().recommend_header_rows(raw)


def parse_preview(
    file_path: str,
    sheet_name: str,
    header_row_index: int | None,
    data_start_row_index: int | None,
    multi_header: bool,
    header_end_row_index: int | None,
):
    parser = _excel_parser()
    try:
        return parser.parse_preview(file_path, sheet_name, header_row_index, data_start_row_index, multi_header, header_end_row_index)
    except parser.ExcelParseError as exc:
        _raise_excel_error(exc)


def parse_rows(
    file_path: str,
    sheet_name: str,
    header_row_index: int,
    data_start_row_index: int,
    multi_header: bool,
    header_end_row_index: int | None,
):
    parser = _excel_parser()
    try:
        return parser.parse_rows(file_path, sheet_name, header_row_index, data_start_row_index, multi_header, header_end_row_index)
    except parser.ExcelParseError as exc:
        _raise_excel_error(exc)


def validate_import_rows(rows, mappings):
    return _import_validator().validate_import_rows(rows, mappings)


def build_abnormal_preview(rows, issues):
    return _import_validator().build_abnormal_preview(rows, issues)


def should_skip_import(row):
    return _import_validator().should_skip_import(row)


def calculate_data_quality_score(db: Session, project_id: int, normalized_rows, field_mappings, issues):
    from app.services.data_quality_service import calculate_data_quality_score as calculate

    return calculate(db, project_id, normalized_rows, field_mappings, issues)


def confirm_import_batch(db: Session, batch: ImportBatch, rows, payload: ImportConfirmRequest):
    from app.services.import_confirm_service import confirm_import_batch as confirm

    return confirm(db, batch, rows, payload)


def build_error_report_workbook(db: Session, batch: ImportBatch):
    from app.services.import_error_report_service import build_error_report_workbook as build

    return build(db, batch)


def apply_ai_fallback_to_columns(db: Session, project_id: int, columns):
    from app.services.ai_column_resolver import apply_ai_fallback_to_columns as apply_fallback

    return apply_fallback(db, project_id=project_id, columns=columns)


class FreezeBatchRequest(BaseModel):
    freeze_remark: str | None = None


def get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前项目不存在或已被清理。")
    return project


def ensure_project_is_not_archived(project: Project) -> None:
    if project.is_archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PROJECT_ARCHIVED", "message": "项目已归档，如需新增导入请先恢复项目。"},
        )


def get_batch_or_404(batch_id: int, db: Session) -> ImportBatch:
    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import batch not found")
    return batch


def raise_excel_parse_error(exc: ExcelParseError) -> None:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": exc.code,
            "message": "未找到指定 Sheet，请重新选择要导入的 Sheet。" if exc.code == "SHEET_NOT_FOUND" else str(exc),
        },
    ) from exc


def _persist_validation_issues(db: Session, batch_id: int, issues) -> None:
    """先清空再批量落 issue，对同一 (row_index, column_name, level, code, message) 做去重。

    重复落库会让用户在 UI 上看到一堆"日期格式可能不正确"的同样提示却分行展示,既占视觉
    又看不出实际有多少独立问题,而且后续按 code 分组统计也会被重复计数污染。
    """
    db.execute(delete(ImportValidationIssue).where(ImportValidationIssue.batch_id == batch_id))
    seen: set[tuple] = set()
    for issue in issues:
        key = (issue.row_index, issue.column_name, issue.level, issue.code, issue.message)
        if key in seen:
            continue
        seen.add(key)
        db.add(
            ImportValidationIssue(
                batch_id=batch_id,
                row_index=issue.row_index,
                column_name=issue.column_name,
                level=issue.level,
                code=issue.code,
                message=issue.message,
            )
        )


def excel_error_message(exc: ExcelParseError) -> str:
    return "未找到指定 Sheet，请重新选择要导入的 Sheet。" if exc.code == "SHEET_NOT_FOUND" else str(exc)


@router.post("/projects/{project_id}/imports/upload", response_model=ImportUploadResponse)
async def upload_import_file(
    project_id: int,
    data_date: date | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ImportUploadResponse:
    project = get_project_or_404(project_id, db)
    ensure_project_is_not_archived(project)
    original_name = file.filename or "upload"
    suffix = Path(original_name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only .xlsx and .csv files are supported")

    project_dir = UPLOAD_DIR / str(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    saved_name = f"{uuid4().hex}{suffix}"
    saved_path = project_dir / saved_name
    content = await file.read()
    # 30MB 上限——经验值,一份正常的工程进度 Excel(明细 + 几个汇总 Sheet)远低于此。
    # 真有客户拿百兆的 Excel 来,大概率是夹了一堆截图或者把整库 dump 进来了,这种文件
    # openpyxl 解析时会把内存打爆,直接 413 拒掉比让用户等半小时然后 OOM 友好得多。
    if len(content) > 30 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"上传文件超出 30MB 限制（当前 {len(content) / 1024 / 1024:.1f}MB），请压缩或拆分后重试。",
        )
    saved_path.write_bytes(content)

    try:
        sheets = get_sheet_names(str(saved_path))
    except ExcelParseError as exc:
        saved_path.unlink(missing_ok=True)
        raise_excel_parse_error(exc)

    batch = ImportBatch(
        project_id=project_id,
        file_name=original_name,
        file_path=str(saved_path),
        data_date=data_date or date.today(),
        status="draft",
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return ImportUploadResponse(batch=batch, sheets=sheets)


@router.get("/projects/{project_id}/imports", response_model=list[ImportBatchRead])
def list_project_imports(
    project_id: int,
    db: Session = Depends(get_db),
) -> list[ImportBatchRead]:
    get_project_or_404(project_id, db)
    batches = list(
        db.query(ImportBatch)
        .filter(ImportBatch.project_id == project_id)
        .order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())
        .limit(20)
    )
    group_counts = _group_sheet_counts(db, project_id, batches)
    return [_batch_read(db, batch, group_counts) for batch in batches]


@router.post("/imports/{batch_id}/freeze", response_model=ImportBatchRead)
def freeze_import_batch(
    batch_id: int,
    payload: FreezeBatchRequest,
    db: Session = Depends(get_db),
) -> ImportBatchRead:
    batch = get_batch_or_404(batch_id, db)
    if batch.status != "published":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅已发布批次可冻结。")
    batch.is_frozen = True
    batch.frozen_at = datetime.now()
    batch.freeze_remark = payload.freeze_remark
    db.add(
        MaintenanceLog(
            action="freeze_batch",
            target_type="import_batch",
            target_id=batch.id,
            summary=f"冻结批次：{batch.sheet_name or batch.file_name}",
            detail=payload.freeze_remark,
        )
    )
    db.commit()
    db.refresh(batch)
    return _batch_read(db, batch)


@router.post("/imports/{batch_id}/unfreeze", response_model=ImportBatchRead)
def unfreeze_import_batch(batch_id: int, db: Session = Depends(get_db)) -> ImportBatchRead:
    batch = get_batch_or_404(batch_id, db)
    batch.is_frozen = False
    batch.frozen_at = None
    batch.freeze_remark = None
    db.add(
        MaintenanceLog(
            action="unfreeze_batch",
            target_type="import_batch",
            target_id=batch.id,
            summary=f"取消冻结批次：{batch.sheet_name or batch.file_name}",
        )
    )
    db.commit()
    db.refresh(batch)
    return _batch_read(db, batch)


@router.post("/imports/{batch_id}/parse", response_model=ImportParseResponse)
def parse_import_batch(
    batch_id: int,
    payload: ImportParseRequest,
    db: Session = Depends(get_db),
) -> ImportParseResponse:
    batch = get_batch_or_404(batch_id, db)
    if not batch.file_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Import batch has no file path")

    try:
        raw = _read_raw(batch.file_path, payload.sheet_name)
        header_row_index, data_start_row_index = resolve_header_rows(
            batch.file_path,
            payload.sheet_name,
            payload.header_row_index,
            payload.data_start_row_index,
        )
        effective_multi_header = payload.multi_header
        effective_header_end_row_index = payload.header_end_row_index
        if not effective_multi_header and effective_header_end_row_index is None:
            inferred_header_end = infer_multi_header_end(raw, header_row_index)
            if inferred_header_end is not None:
                effective_multi_header = True
                effective_header_end_row_index = inferred_header_end
                data_start_row_index = max(data_start_row_index, inferred_header_end + 1)
        header_recommendation = recommend_header_rows(raw)
        columns, preview_rows, row_count = parse_preview(
            batch.file_path,
            payload.sheet_name,
            header_row_index,
            data_start_row_index,
            effective_multi_header,
            effective_header_end_row_index,
        )
    except (ExcelParseError, FileNotFoundError) as exc:
        if isinstance(exc, ExcelParseError):
            raise_excel_parse_error(exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    batch.sheet_name = payload.sheet_name
    if payload.data_date is not None:
        batch.data_date = payload.data_date
    batch.header_row_index = header_row_index
    batch.data_start_row_index = data_start_row_index
    batch.multi_header = effective_multi_header
    batch.header_end_row_index = effective_header_end_row_index
    batch.row_count = row_count
    batch.status = "parsed"
    db.commit()
    db.refresh(batch)

    columns = enrich_columns_with_aliases(db, project_id=batch.project_id, columns=columns)
    columns = apply_ai_fallback_to_columns(db, project_id=batch.project_id, columns=columns)
    matched_templates = match_templates(
        db,
        batch.project_id,
        [column["name"] for column in columns],
        sheet_name=batch.sheet_name,
    )
    field_diagnostics = build_parse_field_diagnostics(batch, columns)

    return ImportParseResponse(
        batch=batch,
        columns=columns,
        preview_rows=preview_rows,
        matched_templates=matched_templates,
        header_recommendation=header_recommendation,
        field_diagnostics=field_diagnostics,
    )


@router.get("/imports/{batch_id}/field-diagnostics")
def field_diagnostics(batch_id: int, db: Session = Depends(get_db)) -> dict:
    batch = get_batch_or_404(batch_id, db)
    items = list(db.query(ProgressItem).filter(ProgressItem.batch_id == batch.id).order_by(ProgressItem.id.asc()))
    fields = []
    if items:
        return build_item_diagnostics(items)
    if batch.file_path and batch.sheet_name and batch.header_row_index is not None and batch.data_start_row_index is not None:
        try:
            columns, _, _ = parse_preview(
                batch.file_path,
                batch.sheet_name,
                batch.header_row_index,
                batch.data_start_row_index,
                batch.multi_header,
                batch.header_end_row_index,
            )
            fields = [
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
        except (ExcelParseError, FileNotFoundError):
            fields = []
    return build_mapping_diagnostics(batch, fields, items)


@router.post("/imports/{file_id}/parse-multiple-sheets", response_model=MultiSheetParseResponse)
def parse_multiple_sheets(
    file_id: int,
    payload: MultiSheetParseRequest,
    db: Session = Depends(get_db),
) -> MultiSheetParseResponse:
    source_batch = get_batch_or_404(file_id, db)
    if source_batch.project_id != payload.project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Import file does not belong to project")
    if not source_batch.file_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Import batch has no file path")
    if not payload.sheet_names:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No sheets selected")

    import_group_id = uuid4().hex
    import_group_name = f"{source_batch.file_name} 多 Sheet 导入"
    results: list[MultiSheetParseResult] = []
    for sheet_name in payload.sheet_names:
        try:
            raw = _read_raw(source_batch.file_path, sheet_name)
            header_recommendation = recommend_header_rows(raw)
            header_row_index, data_start_row_index = resolve_header_rows(
                source_batch.file_path,
                sheet_name,
                payload.header_row_index,
                payload.data_start_row_index,
            )
            effective_multi_header = payload.multi_header
            effective_header_end_row_index = payload.header_end_row_index
            if not effective_multi_header and effective_header_end_row_index is None:
                inferred_header_end = infer_multi_header_end(raw, header_row_index)
                if inferred_header_end is not None:
                    effective_multi_header = True
                    effective_header_end_row_index = inferred_header_end
                    data_start_row_index = max(data_start_row_index, inferred_header_end + 1)
            columns, preview_rows, row_count = parse_preview(
                source_batch.file_path,
                sheet_name,
                header_row_index,
                data_start_row_index,
                effective_multi_header,
                effective_header_end_row_index,
            )
        except ExcelParseError as exc:
            results.append(MultiSheetParseResult(sheet_name=sheet_name, status="error", error=excel_error_message(exc)))
            continue
        except FileNotFoundError as exc:
            results.append(MultiSheetParseResult(sheet_name=sheet_name, status="error", error=str(exc)))
            continue

        batch = ImportBatch(
            project_id=payload.project_id,
            file_name=source_batch.file_name,
            file_path=source_batch.file_path,
            sheet_name=sheet_name,
            import_group_id=import_group_id,
            import_group_name=import_group_name,
            data_date=payload.data_date or source_batch.data_date,
            header_row_index=header_row_index,
            data_start_row_index=data_start_row_index,
            multi_header=effective_multi_header,
            header_end_row_index=effective_header_end_row_index,
            row_count=row_count,
            status="parsed",
            baseline_plan_id=payload.baseline_plan_id,
        )
        db.add(batch)
        db.flush()
        columns = enrich_columns_with_aliases(db, project_id=payload.project_id, columns=columns)
        columns = apply_ai_fallback_to_columns(db, project_id=payload.project_id, columns=columns)
        matched_templates = match_templates(
            db,
            payload.project_id,
            [column["name"] for column in columns],
            sheet_name=sheet_name,
        )
        results.append(
            MultiSheetParseResult(
                sheet_name=sheet_name,
                status="parsed",
                batch_id=batch.id,
                columns=columns,
                preview_rows=preview_rows,
                suggested_mappings=matched_templates,
                header_row_index=header_row_index,
                data_start_row_index=data_start_row_index,
                header_recommendation=header_recommendation,
                row_count=row_count,
            )
        )

    db.commit()
    success_count = sum(1 for result in results if result.status == "parsed")
    return MultiSheetParseResponse(
        import_group_id=import_group_id,
        import_group_name=import_group_name,
        file_id=file_id,
        project_id=payload.project_id,
        total_sheets=len(results),
        success_count=success_count,
        failed_count=len(results) - success_count,
        results=results,
    )


@router.post("/imports/{batch_id}/mapping/validate", response_model=MappingValidationResponse)
def validate_import_mapping(
    batch_id: int,
    payload: MappingValidationRequest,
    db: Session = Depends(get_db),
) -> MappingValidationResponse:
    get_batch_or_404(batch_id, db)
    issues = validate_field_mappings(payload.field_mappings)
    return MappingValidationResponse(
        valid=not any(issue.level == "error" for issue in issues),
        issues=issues,
    )


@router.post("/imports/{batch_id}/validate", response_model=ImportValidationResponse)
def validate_import_batch(
    batch_id: int,
    payload: ImportValidationRequest,
    db: Session = Depends(get_db),
) -> ImportValidationResponse:
    batch = get_batch_or_404(batch_id, db)
    if not payload.field_mappings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "FIELD_MAPPINGS_EMPTY",
                "message": "导入校验失败：字段映射不能为空。",
            },
        )
    if not batch.file_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Import batch has no file path")
    if not batch.sheet_name or batch.header_row_index is None or batch.data_start_row_index is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "SHEET_NOT_SELECTED",
                "message": "请先选择并解析要导入的 Sheet",
            },
        )

    try:
        rows = parse_rows(
            batch.file_path,
            batch.sheet_name,
            batch.header_row_index,
            batch.data_start_row_index,
            batch.multi_header,
            batch.header_end_row_index,
        )
    except (ExcelParseError, FileNotFoundError) as exc:
        if isinstance(exc, ExcelParseError):
            raise_excel_parse_error(exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    issues, normalized_rows = validate_import_rows(rows, payload.field_mappings)
    abnormal_preview = build_abnormal_preview(rows, issues)
    importable_rows = [row for row in normalized_rows if not should_skip_import(row)]
    data_quality = calculate_data_quality_score(db, batch.project_id, importable_rows, payload.field_mappings, issues)
    _persist_validation_issues(db, batch.id, issues)

    warning_count = sum(1 for issue in issues if issue.level == "warning")
    error_count = sum(1 for issue in issues if issue.level == "error")
    batch.warning_count = warning_count
    batch.error_count = error_count
    batch.skipped_count = sum(1 for row in normalized_rows if should_skip_import(row))
    batch.data_quality_score = data_quality.data_quality_score
    batch.field_completeness = data_quality.field_completeness
    batch.task_match_rate = data_quality.task_match_rate
    batch.valid_row_rate = data_quality.valid_row_rate
    batch.plan_field_completeness = data_quality.plan_field_completeness
    batch.unit_consistency = data_quality.unit_consistency
    batch.status = "validated" if error_count == 0 else "parsed"
    db.commit()

    return ImportValidationResponse(
        valid=error_count == 0,
        warning_count=warning_count,
        error_count=error_count,
        data_quality=data_quality,
        issues=issues,
        issue_code_counts=summarize_issue_codes(issues),
        abnormal_preview=abnormal_preview,
        normalized_preview_rows=normalized_rows[:20],
    )


@router.get("/imports/{batch_id}/error-report")
def download_import_error_report(
    batch_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """导出当前批次的行级校验错误清单 Excel。

    现场人员可以拿着这份清单回到 Excel 原表里逐行修正：
    每条 issue 一行，附带行号、错误码、错误说明、列名、原始值与整行原始数据。
    """
    batch = get_batch_or_404(batch_id, db)
    content = build_error_report_workbook(db, batch)
    filename = _error_report_filename(batch)
    quoted = quote(filename)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=\"error-report.xlsx\"; filename*=UTF-8''{quoted}",
        },
    )


def _error_report_filename(batch: ImportBatch) -> str:
    stem = batch.sheet_name or batch.file_name or f"batch-{batch.id}"
    safe = stem.replace("/", "_").replace("\\", "_").strip() or f"batch-{batch.id}"
    return f"{safe}-错误清单.xlsx"


@router.post("/imports/validate-multiple-sheets", response_model=MultiSheetValidationResponse)
def validate_multiple_sheets(
    payload: MultiSheetValidationRequest,
    db: Session = Depends(get_db),
) -> MultiSheetValidationResponse:
    results: list[MultiSheetValidationResult] = []
    for sheet_payload in payload.sheets:
        batch = db.get(ImportBatch, sheet_payload.batch_id)
        if batch is None:
            results.append(
                MultiSheetValidationResult(
                    sheet_name=sheet_payload.sheet_name,
                    batch_id=sheet_payload.batch_id,
                    valid=False,
                    error_count=1,
                    error="Import batch not found",
                )
            )
            continue
        if not sheet_payload.mappings:
            results.append(
                MultiSheetValidationResult(
                    sheet_name=sheet_payload.sheet_name,
                    batch_id=batch.id,
                    valid=False,
                    error_count=1,
                    error="字段映射不能为空。",
                )
            )
            continue
        if not batch.file_path or not batch.sheet_name:
            results.append(
                MultiSheetValidationResult(
                    sheet_name=sheet_payload.sheet_name,
                    batch_id=batch.id,
                    valid=False,
                    error_count=1,
                    error="请先选择并解析要导入的 Sheet",
                )
            )
            continue

        if sheet_payload.header_row_index is not None:
            batch.header_row_index = sheet_payload.header_row_index
        if sheet_payload.data_start_row_index is not None:
            batch.data_start_row_index = sheet_payload.data_start_row_index
        if batch.header_row_index is None or batch.data_start_row_index is None:
            results.append(
                MultiSheetValidationResult(
                    sheet_name=sheet_payload.sheet_name,
                    batch_id=batch.id,
                    valid=False,
                    error_count=1,
                    error="请先解析表头行和数据起始行",
                )
            )
            continue

        try:
            rows = parse_rows(
                batch.file_path,
                batch.sheet_name,
                batch.header_row_index,
                batch.data_start_row_index,
                batch.multi_header,
                batch.header_end_row_index,
            )
        except ExcelParseError as exc:
            results.append(
                MultiSheetValidationResult(
                    sheet_name=sheet_payload.sheet_name,
                    batch_id=batch.id,
                    valid=False,
                    error_count=1,
                    error=excel_error_message(exc),
                )
            )
            continue
        except FileNotFoundError as exc:
            results.append(
                MultiSheetValidationResult(
                    sheet_name=sheet_payload.sheet_name,
                    batch_id=batch.id,
                    valid=False,
                    error_count=1,
                    error=str(exc),
                )
            )
            continue

        issues, normalized_rows = validate_import_rows(rows, sheet_payload.mappings)
        abnormal_preview = build_abnormal_preview(rows, issues)
        importable_rows = [row for row in normalized_rows if not should_skip_import(row)]
        data_quality = calculate_data_quality_score(db, batch.project_id, importable_rows, sheet_payload.mappings, issues)
        _persist_validation_issues(db, batch.id, issues)
        warning_count = sum(1 for issue in issues if issue.level == "warning")
        error_count = sum(1 for issue in issues if issue.level == "error")
        skipped_count = sum(1 for row in normalized_rows if should_skip_import(row))
        batch.warning_count = warning_count
        batch.error_count = error_count
        batch.skipped_count = skipped_count
        batch.data_quality_score = data_quality.data_quality_score
        batch.field_completeness = data_quality.field_completeness
        batch.task_match_rate = data_quality.task_match_rate
        batch.valid_row_rate = data_quality.valid_row_rate
        batch.plan_field_completeness = data_quality.plan_field_completeness
        batch.unit_consistency = data_quality.unit_consistency
        batch.status = "validated" if error_count == 0 else "parsed"
        results.append(
            MultiSheetValidationResult(
                sheet_name=batch.sheet_name,
                batch_id=batch.id,
                valid=error_count == 0,
                warning_count=warning_count,
                error_count=error_count,
                skipped_count=skipped_count,
                data_quality_score=data_quality.data_quality_score,
                issues=issues,
                abnormal_preview=abnormal_preview,
            )
        )

    db.commit()
    success_count = sum(1 for result in results if result.valid)
    return MultiSheetValidationResponse(
        total_sheets=len(results),
        success_count=success_count,
        failed_count=len(results) - success_count,
        results=results,
    )


@router.post("/imports/{batch_id}/confirm", response_model=ImportConfirmResponse)
def confirm_import(
    batch_id: int,
    payload: ImportConfirmRequest,
    db: Session = Depends(get_db),
) -> ImportConfirmResponse:
    batch = get_batch_or_404(batch_id, db)
    if batch.is_frozen:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前批次已冻结，不允许覆盖或重新导入。")
    if batch.status == "imported" and payload.import_strategy != "overwrite_current":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Imported batches can only be re-imported with overwrite_current strategy",
        )
    if not batch.file_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Import batch has no file path")
    if not batch.sheet_name or batch.header_row_index is None or batch.data_start_row_index is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "SHEET_NOT_SELECTED",
                "message": "请先选择并解析要导入的 Sheet",
            },
        )

    try:
        rows = parse_rows(
            batch.file_path,
            batch.sheet_name,
            batch.header_row_index,
            batch.data_start_row_index,
            batch.multi_header,
            batch.header_end_row_index,
        )
    except (ExcelParseError, FileNotFoundError) as exc:
        if isinstance(exc, ExcelParseError):
            raise_excel_parse_error(exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if payload.data_date is not None:
        batch.data_date = payload.data_date
    if payload.sheet_name is None:
        payload.sheet_name = batch.sheet_name
    try:
        response = confirm_import_batch(db, batch, rows, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return response


@router.post("/imports/confirm-multiple-sheets", response_model=MultiSheetConfirmResponse)
def confirm_multiple_sheets(
    payload: MultiSheetConfirmRequest,
    db: Session = Depends(get_db),
) -> MultiSheetConfirmResponse:
    get_project_or_404(payload.project_id, db)
    results: list[MultiSheetConfirmBatchResult] = []
    for sheet_payload in payload.sheets:
        batch = db.get(ImportBatch, sheet_payload.batch_id)
        if batch is None:
            results.append(
                MultiSheetConfirmBatchResult(
                    sheet_name=sheet_payload.sheet_name,
                    batch_id=sheet_payload.batch_id,
                    status="failed",
                    error="Import batch not found",
                )
            )
            continue
        if batch.project_id != payload.project_id:
            results.append(
                MultiSheetConfirmBatchResult(
                    sheet_name=sheet_payload.sheet_name,
                    batch_id=batch.id,
                    status="failed",
                    error="Import batch does not belong to project",
                )
            )
            continue
        if batch.is_frozen:
            results.append(
                MultiSheetConfirmBatchResult(
                    sheet_name=sheet_payload.sheet_name,
                    batch_id=batch.id,
                    status="failed",
                    error="当前批次已冻结，不允许覆盖或重新导入。",
                )
            )
            continue
        if not batch.file_path or not batch.sheet_name or batch.header_row_index is None or batch.data_start_row_index is None:
            results.append(
                MultiSheetConfirmBatchResult(
                    sheet_name=sheet_payload.sheet_name,
                    batch_id=batch.id,
                    status="failed",
                    error="请先选择并解析要导入的 Sheet",
                )
            )
            continue
        if batch.error_count > 0:
            results.append(
                MultiSheetConfirmBatchResult(
                    sheet_name=sheet_payload.sheet_name,
                    batch_id=batch.id,
                    status="failed",
                    warning_count=batch.warning_count,
                    error_count=batch.error_count,
                    skipped_count=batch.skipped_count,
                    error="存在校验错误，未导入。请修正 error 后重新校验。",
                )
            )
            continue

        try:
            rows = parse_rows(
                batch.file_path,
                batch.sheet_name,
                batch.header_row_index,
                batch.data_start_row_index,
                batch.multi_header,
                batch.header_end_row_index,
            )
        except ExcelParseError as exc:
            results.append(
                MultiSheetConfirmBatchResult(
                    sheet_name=sheet_payload.sheet_name,
                    batch_id=batch.id,
                    status="failed",
                    error=excel_error_message(exc),
                )
            )
            continue
        except FileNotFoundError as exc:
            results.append(
                MultiSheetConfirmBatchResult(
                    sheet_name=sheet_payload.sheet_name,
                    batch_id=batch.id,
                    status="failed",
                    error=str(exc),
                )
            )
            continue

        if payload.data_date is not None:
            batch.data_date = payload.data_date
        confirm_payload = ImportConfirmRequest(
            template_name=sheet_payload.template_name,
            save_as_template=sheet_payload.save_template,
            sheet_name=batch.sheet_name,
            data_date=payload.data_date,
            calculation_profile_id=payload.calculation_profile_id,
            baseline_plan_id=payload.baseline_plan_id,
            mapping_template_id=sheet_payload.mapping_template_id,
            import_strategy=sheet_payload.import_strategy,
            field_mappings=sheet_payload.mappings,
        )
        try:
            response = confirm_import_batch(db, batch, rows, confirm_payload)
        except ValueError as exc:
            results.append(
                MultiSheetConfirmBatchResult(
                    sheet_name=batch.sheet_name,
                    batch_id=batch.id,
                    status="failed",
                    error=str(exc),
                )
            )
            continue
        if response.valid:
            results.append(
                MultiSheetConfirmBatchResult(
                    sheet_name=batch.sheet_name,
                    batch_id=batch.id,
                    imported_count=response.imported_count,
                    skipped_count=response.skipped_count,
                    warning_count=response.warning_count,
                    error_count=response.error_count,
                    status=response.status,
                )
            )
        else:
            if response.error_count > 0:
                error_message = "存在校验错误，不能发布。点击查看具体错误。"
            elif response.imported_count == 0 and response.skipped_count > 0:
                error_message = "未生成有效进度数据，可能是辅助 Sheet 或非进度明细表，不建议发布。"
            else:
                error_message = "正式导入失败，请检查字段映射和原始数据。"
            results.append(
                MultiSheetConfirmBatchResult(
                    sheet_name=batch.sheet_name,
                    batch_id=batch.id,
                    imported_count=response.imported_count,
                    skipped_count=response.skipped_count,
                    warning_count=response.warning_count,
                    error_count=response.error_count,
                    status="failed",
                    error=error_message,
                )
            )

    db.commit()
    success_count = sum(1 for result in results if result.status == "imported")
    return MultiSheetConfirmResponse(
        total_sheets=len(results),
        success_count=success_count,
        failed_count=len(results) - success_count,
        batches=results,
    )


@router.post("/imports/{batch_id}/publish", response_model=ImportPublishResponse)
def publish_import_batch(
    batch_id: int,
    db: Session = Depends(get_db),
) -> ImportPublishResponse:
    batch = get_batch_or_404(batch_id, db)
    if not batch.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive batches cannot be published",
        )
    if batch.error_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="存在校验错误，未导入，不能发布。",
        )
    if batch.imported_count <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未生成有效进度数据，不能发布。该 Sheet 可能不是进度明细表。",
        )
    if batch.status != "imported":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only imported batches can be published",
        )

    published_at = datetime.now()
    # CAS:只在 status 仍然是 imported 时才能翻成 published——避免两个并发请求(双击发布
    # 按钮、两个浏览器标签同时操作)都通过前面的状态检查后,各自走一遍下面的写入逻辑,
    # 导致 audit log 出现重复条目、published_at 被覆盖等问题。
    cas_result = db.execute(
        update(ImportBatch)
        .where(ImportBatch.id == batch.id, ImportBatch.status == "imported")
        .values(
            status="published",
            published_by="system",
            published_at=published_at,
        )
    )
    if cas_result.rowcount == 0:
        db.rollback()
        # 重新读一份最新状态告诉用户
        latest = db.get(ImportBatch, batch.id)
        if latest is not None and latest.status == "published":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="该批次已被另一请求发布,请刷新页面查看最新状态。",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="批次状态在发布过程中被改变,请刷新页面后重试。",
        )
    db.refresh(batch)
    db.add(
        AuditLog(
            project_id=batch.project_id,
            entity_type="import_batch",
            entity_id=batch.id,
            action="publish_import",
            detail=json.dumps(
                {
                    "status": "published",
                    "is_active": batch.is_active,
                    "imported_count": batch.imported_count,
                    "data_quality_score": batch.data_quality_score,
                },
                ensure_ascii=False,
            ),
            created_by="system",
        )
    )
    db.commit()
    db.refresh(batch)

    return ImportPublishResponse(
        id=batch.id,
        project_id=batch.project_id,
        status=batch.status,
        is_active=batch.is_active,
        imported_count=batch.imported_count,
        warning_count=batch.warning_count,
        error_count=batch.error_count,
        data_quality_score=batch.data_quality_score,
        published_by=batch.published_by,
        published_at=batch.published_at or published_at,
    )


@router.post("/imports/publish-multiple-sheets", response_model=MultiSheetPublishResponse)
def publish_multiple_sheets(
    batch_ids: list[int],
    db: Session = Depends(get_db),
) -> MultiSheetPublishResponse:
    results: list[MultiSheetPublishResult] = []
    for batch_id in batch_ids:
        batch = db.get(ImportBatch, batch_id)
        if batch is None:
            results.append(
                MultiSheetPublishResult(
                    batch_id=batch_id,
                    status="publish_failed",
                    published=False,
                    error="导入批次不存在，无法发布。",
                )
            )
            continue
        if batch.status != "imported":
            results.append(
                MultiSheetPublishResult(
                    batch_id=batch.id,
                    sheet_name=batch.sheet_name,
                    status="publish_failed",
                    published=False,
                    error="只有导入成功的批次可以发布。",
                )
            )
            continue
        if not batch.is_active:
            results.append(
                MultiSheetPublishResult(
                    batch_id=batch.id,
                    sheet_name=batch.sheet_name,
                    status="publish_failed",
                    published=False,
                    error="该批次已停用，无法发布。",
                )
            )
            continue
        if batch.error_count > 0:
            results.append(
                MultiSheetPublishResult(
                    batch_id=batch.id,
                    sheet_name=batch.sheet_name,
                    status="unpublishable",
                    published=False,
                    error="存在校验错误，未导入，不能发布。",
                )
            )
            continue
        if batch.imported_count <= 0:
            results.append(
                MultiSheetPublishResult(
                    batch_id=batch.id,
                    sheet_name=batch.sheet_name,
                    status="unpublishable",
                    published=False,
                    error="未生成有效进度数据，不能发布。该 Sheet 可能不是进度明细表。",
                )
            )
            continue
        published_at = datetime.now()
        batch.status = "published"
        batch.published_by = "system"
        batch.published_at = published_at
        db.add(
            AuditLog(
                project_id=batch.project_id,
                entity_type="import_batch",
                entity_id=batch.id,
                action="publish_import",
                detail=json.dumps(
                    {
                        "status": "published",
                        "is_active": batch.is_active,
                        "imported_count": batch.imported_count,
                        "data_quality_score": batch.data_quality_score,
                    },
                    ensure_ascii=False,
                ),
                created_by="system",
            )
        )
        publish_response = ImportPublishResponse(
            id=batch.id,
            project_id=batch.project_id,
            status=batch.status,
            is_active=batch.is_active,
            imported_count=batch.imported_count,
            warning_count=batch.warning_count,
            error_count=batch.error_count,
            data_quality_score=batch.data_quality_score,
            published_by=batch.published_by,
            published_at=batch.published_at or published_at,
        )
        results.append(
            MultiSheetPublishResult(
                batch_id=batch.id,
                sheet_name=batch.sheet_name,
                status=batch.status,
                published=True,
                result=publish_response,
            )
        )
    db.commit()
    published_count = sum(1 for result in results if result.published)
    return MultiSheetPublishResponse(
        total_count=len(results),
        published_count=published_count,
        failed_publish_count=len(results) - published_count,
        results=results,
    )


def _group_sheet_counts(db: Session, project_id: int, batches: list[ImportBatch]) -> dict[str, int]:
    group_ids = [batch.import_group_id for batch in batches if batch.import_group_id]
    if not group_ids:
        return {}
    rows = (
        db.query(ImportBatch.import_group_id, ImportBatch.id)
        .filter(ImportBatch.project_id == project_id, ImportBatch.import_group_id.in_(group_ids))
        .all()
    )
    counts: dict[str, set[int]] = {}
    for group_id, batch_id in rows:
        if group_id:
            counts.setdefault(group_id, set()).add(batch_id)
    return {group_id: len(batch_ids) for group_id, batch_ids in counts.items()}


def _batch_read(db: Session, batch: ImportBatch, group_counts: dict[str, int] | None = None) -> ImportBatchRead:
    baseline_name = None
    if batch.baseline_plan_id:
        from app.models.baseline_plan import BaselinePlan

        baseline = db.get(BaselinePlan, batch.baseline_plan_id)
        baseline_name = baseline.name if baseline else None
    group_sheet_count = group_counts.get(batch.import_group_id, 1) if group_counts and batch.import_group_id else 1
    return ImportBatchRead.model_validate(batch).model_copy(
        update={
            "baseline_plan_name": baseline_name,
            "is_multi_sheet": bool(batch.import_group_id),
            "group_sheet_count": group_sheet_count,
        },
    )
