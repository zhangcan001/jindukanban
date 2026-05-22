from datetime import date, datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import delete, exists, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.ai_call_log import AiCallLog
from app.models.ai_prompt_template import AiPromptTemplate
from app.models.baseline_plan import BaselinePlan
from app.models.calculation_profile import CalculationProfile
from app.models.import_batch import ImportBatch
from app.models.import_validation_issue import ImportValidationIssue
from app.models.maintenance_log import MaintenanceLog
from app.models.mapping_field import MappingField
from app.models.mapping_template import MappingTemplate
from app.models.progress_item_edit_history import ProgressItemEditHistory
from app.models.progress_item import ProgressItem
from app.models.progress_task import ProgressTask
from app.models.project import Project
from app.models.raw_import_row import RawImportRow
from app.models.rectification_action_log import RectificationActionLog
from app.models.rectification_item import RectificationItem
from app.models.project_template import ProjectTemplate
from app.models.report_export_record import ReportExportRecord
from app.models.standard_dictionary import StandardDictionary
from app.models.warning_record import WarningRecord
from app.models.warning_rule import WarningRule
from app.schemas.project import ProjectArchiveRequest, ProjectCreate, ProjectRead, ProjectUpdate
from app.services.project_template_service import apply_project_template

router = APIRouter(prefix="/projects", tags=["projects"])


def get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PROJECT_NOT_FOUND", "message": "当前项目不存在或已被清理。"},
        )
    return project


def validate_project_defaults(project: Project, db: Session) -> None:
    allowed_methods = {"auto", "weighted_percent", "value_weighted_percent", "quantity_percent", "percent_average", "task_average", None, ""}
    if project.default_calculation_method not in allowed_methods:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Default calculation method is not supported",
        )

    if project.default_calculation_profile_id is not None:
        profile = db.get(CalculationProfile, project.default_calculation_profile_id)
        if profile is None or profile.project_id != project.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Default calculation profile does not belong to this project",
            )

    if project.default_baseline_plan_id is not None:
        baseline = db.get(BaselinePlan, project.default_baseline_plan_id)
        if baseline is None or baseline.project_id != project.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Default baseline plan does not belong to this project",
            )


def ensure_project_can_be_deleted(project_id: int, db: Session) -> None:
    related_checks = (
        ImportBatch,
        ProgressTask,
        ProgressItem,
        WarningRecord,
        ReportExportRecord,
    )
    for model in related_checks:
        has_related_data = db.scalar(select(exists().where(model.project_id == project_id)))
        if has_related_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "PROJECT_HAS_RELATED_DATA",
                    "message": "该项目已有导入数据，不能直接删除。请先停用或清理相关数据。",
                },
            )


def _confirm_force_delete(confirm_text: str | None) -> None:
    if confirm_text != "确认删除项目":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "DELETE_CONFIRM_MISMATCH", "message": "确认文字不匹配，已拒绝删除。请输入“确认删除项目”。"},
        )


def _delete_project_related_data(db: Session, project_id: int) -> dict[str, int]:
    deleted_counts = {
        "import_batches": _count_for_project(db, ImportBatch, project_id),
        "progress_items": _count_for_project(db, ProgressItem, project_id),
        "warnings": _count_for_project(db, WarningRecord, project_id),
        "rectifications": _count_for_project(db, RectificationItem, project_id),
        "reports": _count_for_project(db, ReportExportRecord, project_id),
        "baselines": _count_for_project(db, BaselinePlan, project_id),
    }

    batch_ids = list(db.scalars(select(ImportBatch.id).where(ImportBatch.project_id == project_id)).all())
    progress_item_ids = list(db.scalars(select(ProgressItem.id).where(ProgressItem.project_id == project_id)).all())
    rectification_item_ids = list(db.scalars(select(RectificationItem.id).where(RectificationItem.project_id == project_id)).all())

    if progress_item_ids:
        db.execute(delete(ProgressItemEditHistory).where(ProgressItemEditHistory.progress_item_id.in_(progress_item_ids)))
    if rectification_item_ids:
        db.execute(delete(RectificationActionLog).where(RectificationActionLog.rectification_item_id.in_(rectification_item_ids)))
    db.execute(delete(RectificationActionLog).where(RectificationActionLog.project_id == project_id))
    db.execute(delete(RectificationItem).where(RectificationItem.project_id == project_id))
    db.execute(delete(WarningRecord).where(WarningRecord.project_id == project_id))
    db.execute(delete(ReportExportRecord).where(ReportExportRecord.project_id == project_id))

    if batch_ids:
        db.execute(delete(ImportValidationIssue).where(ImportValidationIssue.batch_id.in_(batch_ids)))
        db.execute(delete(RawImportRow).where(RawImportRow.batch_id.in_(batch_ids)))

    template_ids = list(db.scalars(select(MappingTemplate.id).where(MappingTemplate.project_id == project_id)).all())
    if template_ids:
        db.execute(delete(MappingField).where(MappingField.template_id.in_(template_ids)))
        db.execute(delete(MappingTemplate).where(MappingTemplate.id.in_(template_ids)))

    db.execute(delete(WarningRule).where(WarningRule.project_id == project_id))
    db.execute(delete(ProgressItem).where(ProgressItem.project_id == project_id))
    if batch_ids:
        db.execute(delete(ImportBatch).where(ImportBatch.id.in_(batch_ids)))
    db.execute(delete(ProgressTask).where(ProgressTask.project_id == project_id))
    db.execute(delete(BaselinePlan).where(BaselinePlan.project_id == project_id))
    db.execute(delete(CalculationProfile).where(CalculationProfile.project_id == project_id))
    db.execute(delete(AuditLog).where(AuditLog.project_id == project_id))
    db.execute(delete(StandardDictionary).where(StandardDictionary.project_id == project_id))
    db.execute(delete(AiCallLog).where(AiCallLog.project_id == project_id))
    db.execute(delete(AiPromptTemplate).where(AiPromptTemplate.project_id == project_id))
    db.execute(delete(Project).where(Project.id == project_id))
    return deleted_counts


def _count_for_project(db: Session, model: type, project_id: int) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(model.project_id == project_id)) or 0)


def _write_maintenance_log(
    db: Session,
    action: str,
    target_type: str,
    target_id: int,
    summary: str,
    detail: str | None = None,
) -> None:
    db.add(MaintenanceLog(action=action, target_type=target_type, target_id=target_id, summary=summary, detail=detail))


def _create_default_demo_baseline(db: Session, project: Project) -> BaselinePlan:
    baseline = BaselinePlan(
        project_id=project.id,
        name="默认计划基线",
        plan_type="current",
        description="示例项目默认计划基线，可用于导入 sample_data 示例进度表后查看 Dashboard 与报表。",
        baseline_date=date.today(),
        is_default=True,
        is_active=True,
    )
    db.add(baseline)
    db.flush()
    project.default_baseline_plan_id = baseline.id
    return baseline


@router.get("", response_model=list[ProjectRead])
def list_projects(include_archived: bool = Query(False), db: Session = Depends(get_db)) -> list[Project]:
    statement = select(Project)
    if not include_archived:
        statement = statement.where(Project.is_archived.is_(False))
    statement = statement.order_by(Project.created_at.desc(), Project.id.desc())
    return list(db.scalars(statement).all())


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    project = Project(**payload.model_dump())
    template_id = project.template_id
    template = db.get(ProjectTemplate, template_id) if template_id else None
    if template_id and (template is None or not template.is_active):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="项目模板不存在或已停用。")
    db.add(project)
    db.flush()
    validate_project_defaults(project, db)
    if template is not None:
        apply_project_template(db, project, template)
    db.commit()
    db.refresh(project)
    return project


@router.post("/demo", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_demo_project(db: Session = Depends(get_db)) -> Project:
    project = Project(
        name="示例项目 - 机电进度管理",
        project_type="机电安装",
        owner_unit="示例建设单位",
        supervision_unit="示例监理单位",
        construction_unit="示例施工单位",
        start_date=date(2026, 5, 1),
        planned_finish_date=date(2026, 8, 31),
        remark="demo 示例项目；可归档、删除或通过测试项目清理识别。请使用 sample_data 目录中的示例 Excel 体验导入流程。",
        created_by="demo-onboarding",
    )
    db.add(project)
    db.flush()
    _create_default_demo_baseline(db, project)
    _write_maintenance_log(
        db,
        "create_demo_project",
        "project",
        project.id,
        f"创建示例项目：{project.name}",
        "已自动创建默认计划基线；建议导入 sample_data 示例 Excel。",
    )
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, db: Session = Depends(get_db)) -> Project:
    return get_project_or_404(project_id, db)


@router.put("/{project_id}", response_model=ProjectRead)
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)) -> Project:
    project = get_project_or_404(project_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)

    validate_project_defaults(project, db)
    db.commit()
    db.refresh(project)
    return project


@router.post("/{project_id}/archive", response_model=ProjectRead)
def archive_project(project_id: int, payload: ProjectArchiveRequest, db: Session = Depends(get_db)) -> Project:
    project = get_project_or_404(project_id, db)
    project.is_archived = True
    project.archived_at = datetime.now()
    project.archive_remark = payload.archive_remark
    _write_maintenance_log(db, "archive_project", "project", project.id, f"归档项目：{project.name}", payload.archive_remark)
    db.commit()
    db.refresh(project)
    return project


@router.post("/{project_id}/restore", response_model=ProjectRead)
def restore_project(project_id: int, db: Session = Depends(get_db)) -> Project:
    project = get_project_or_404(project_id, db)
    project.is_archived = False
    project.archived_at = None
    project.archive_remark = None
    _write_maintenance_log(db, "restore_project", "project", project.id, f"恢复项目：{project.name}")
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db)) -> None:
    project = get_project_or_404(project_id, db)
    ensure_project_can_be_deleted(project_id, db)
    db.delete(project)
    db.commit()


class ProjectForceDeleteRequest(BaseModel):
    confirm_text: str | None = None


@router.delete("/{project_id}/force")
def force_delete_project(
    project_id: int,
    payload: ProjectForceDeleteRequest = Body(...),
    db: Session = Depends(get_db),
) -> dict:
    project = get_project_or_404(project_id, db)
    _confirm_force_delete(payload.confirm_text)
    deleted_counts = _delete_project_related_data(db, project_id)
    _write_maintenance_log(
        db,
        "force_delete_project",
        "project",
        project_id,
        f"强制删除项目：{project.name}",
        "项目及关联数据已删除。",
    )
    db.commit()
    return {
        "deleted": True,
        "project_id": project_id,
        "deleted_counts": deleted_counts,
        "message": "项目及关联数据已删除。",
    }
