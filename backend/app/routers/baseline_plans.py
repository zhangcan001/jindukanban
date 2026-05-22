from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.baseline_plan import BaselinePlan
from app.models.baseline_plan_snapshot import BaselinePlanSnapshot
from app.models.import_batch import ImportBatch
from app.models.project import Project
from app.schemas.baseline_plan import BaselineBoundBatch, BaselinePlanCreate, BaselinePlanRead, BaselinePlanUpdate
from app.schemas.baseline_snapshot import BaselineSnapshotCreate, BaselineSnapshotDiff, BaselineSnapshotRead
from app.services.baseline_snapshot_service import (
    compute_snapshot_diff,
    create_snapshot,
    list_snapshots,
)

router = APIRouter(prefix="/projects/{project_id}/baseline-plans", tags=["baseline plans"])


def get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前项目不存在或已被清理。")
    return project


def get_baseline_or_404(project_id: int, baseline_id: int, db: Session) -> BaselinePlan:
    baseline = db.get(BaselinePlan, baseline_id)
    if baseline is None or baseline.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baseline plan not found")
    return baseline


def apply_default_baseline(project: Project, baseline: BaselinePlan, db: Session) -> None:
    statement = select(BaselinePlan).where(BaselinePlan.project_id == project.id)
    for item in db.scalars(statement):
        item.is_default = item.id == baseline.id
    project.default_baseline_plan_id = baseline.id


@router.get("", response_model=list[BaselinePlanRead])
def list_baseline_plans(project_id: int, db: Session = Depends(get_db)) -> list[BaselinePlanRead]:
    get_project_or_404(project_id, db)
    statement = (
        select(BaselinePlan)
        .where(BaselinePlan.project_id == project_id)
        .order_by(BaselinePlan.is_default.desc(), BaselinePlan.id.desc())
    )
    baselines = list(db.scalars(statement).all())
    return [_read_baseline(db, baseline) for baseline in baselines]


@router.post("", response_model=BaselinePlanRead, status_code=status.HTTP_201_CREATED)
def create_baseline_plan(
    project_id: int,
    payload: BaselinePlanCreate,
    db: Session = Depends(get_db),
) -> BaselinePlanRead:
    project = get_project_or_404(project_id, db)
    if project.is_archived:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="项目已归档，不能新建计划基线。")
    baseline = BaselinePlan(project_id=project_id, **payload.model_dump())
    db.add(baseline)
    db.flush()

    has_default = project.default_baseline_plan_id is not None
    if payload.is_default or not has_default:
        apply_default_baseline(project, baseline, db)

    db.commit()
    db.refresh(baseline)
    return _read_baseline(db, baseline)


@router.get("/{baseline_id}/batches", response_model=list[BaselineBoundBatch])
def list_baseline_bound_batches(project_id: int, baseline_id: int, db: Session = Depends(get_db)) -> list[BaselineBoundBatch]:
    get_project_or_404(project_id, db)
    get_baseline_or_404(project_id, baseline_id, db)
    statement = (
        select(ImportBatch)
        .where(ImportBatch.project_id == project_id, ImportBatch.baseline_plan_id == baseline_id)
        .order_by(ImportBatch.data_date.desc().nullslast(), ImportBatch.created_at.desc(), ImportBatch.id.desc())
    )
    baseline = get_baseline_or_404(project_id, baseline_id, db)
    return [_read_bound_batch(batch, baseline.name) for batch in db.scalars(statement).all()]


@router.get("/{baseline_id}", response_model=BaselinePlanRead)
def get_baseline_plan(project_id: int, baseline_id: int, db: Session = Depends(get_db)) -> BaselinePlanRead:
    get_project_or_404(project_id, db)
    return _read_baseline(db, get_baseline_or_404(project_id, baseline_id, db))


@router.put("/{baseline_id}", response_model=BaselinePlanRead)
def update_baseline_plan(
    project_id: int,
    baseline_id: int,
    payload: BaselinePlanUpdate,
    db: Session = Depends(get_db),
) -> BaselinePlanRead:
    project = get_project_or_404(project_id, db)
    baseline = get_baseline_or_404(project_id, baseline_id, db)
    update_data = payload.model_dump(exclude_unset=True)
    requested_default = update_data.pop("is_default", None)
    for field, value in update_data.items():
        setattr(baseline, field, value)

    if requested_default is True:
        apply_default_baseline(project, baseline, db)
    elif requested_default is False and project.default_baseline_plan_id == baseline.id:
        project.default_baseline_plan_id = None
        baseline.is_default = False

    if update_data.get("is_active") is False and project.default_baseline_plan_id == baseline.id:
        _clear_or_promote_default(project, baseline, db)
    elif update_data.get("is_active") is False and baseline.is_default:
        _clear_or_promote_default(project, baseline, db)

    db.commit()
    db.refresh(baseline)
    return _read_baseline(db, baseline)


@router.delete("/{baseline_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_baseline_plan(project_id: int, baseline_id: int, db: Session = Depends(get_db)) -> None:
    project = get_project_or_404(project_id, db)
    baseline = get_baseline_or_404(project_id, baseline_id, db)
    if project.default_baseline_plan_id == baseline.id:
        _clear_or_promote_default(project, baseline, db)
    db.delete(baseline)
    db.commit()


@router.post(
    "/{baseline_id}/snapshots",
    response_model=BaselineSnapshotRead,
    status_code=status.HTTP_201_CREATED,
)
def create_baseline_snapshot(
    project_id: int,
    baseline_id: int,
    payload: BaselineSnapshotCreate,
    db: Session = Depends(get_db),
) -> BaselineSnapshotRead:
    get_project_or_404(project_id, db)
    baseline = get_baseline_or_404(project_id, baseline_id, db)
    snapshot = create_snapshot(
        db,
        baseline,
        label=payload.label,
        description=payload.description,
        snapshot_date=payload.snapshot_date,
        created_by=payload.created_by,
    )
    db.commit()
    db.refresh(snapshot)
    return BaselineSnapshotRead.model_validate(snapshot)


@router.get("/{baseline_id}/snapshots", response_model=list[BaselineSnapshotRead])
def list_baseline_snapshots(
    project_id: int,
    baseline_id: int,
    db: Session = Depends(get_db),
) -> list[BaselineSnapshotRead]:
    get_project_or_404(project_id, db)
    get_baseline_or_404(project_id, baseline_id, db)
    snapshots = list_snapshots(db, baseline_id)
    return [BaselineSnapshotRead.model_validate(snapshot) for snapshot in snapshots]


@router.get(
    "/{baseline_id}/snapshots/{snapshot_id}/diff",
    response_model=BaselineSnapshotDiff,
)
def diff_baseline_snapshot(
    project_id: int,
    baseline_id: int,
    snapshot_id: int,
    db: Session = Depends(get_db),
) -> BaselineSnapshotDiff:
    get_project_or_404(project_id, db)
    get_baseline_or_404(project_id, baseline_id, db)
    snapshot = db.get(BaselinePlanSnapshot, snapshot_id)
    if snapshot is None or snapshot.baseline_plan_id != baseline_id or snapshot.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="快照不存在或已被清理。")
    diff = compute_snapshot_diff(db, snapshot)
    return BaselineSnapshotDiff.model_validate(diff)


def _clear_or_promote_default(project: Project, baseline: BaselinePlan, db: Session) -> None:
    candidates = list(
        db.scalars(
            select(BaselinePlan)
            .where(
                BaselinePlan.project_id == project.id,
                BaselinePlan.id != baseline.id,
                BaselinePlan.is_active.is_(True),
            )
            .order_by(BaselinePlan.is_default.desc(), BaselinePlan.id.desc())
        ).all()
    )
    if candidates:
        apply_default_baseline(project, candidates[0], db)
    else:
        project.default_baseline_plan_id = None
        baseline.is_default = False


def _read_baseline(db: Session, baseline: BaselinePlan) -> BaselinePlanRead:
    count = db.scalar(
        select(func.count(ImportBatch.id)).where(
            ImportBatch.project_id == baseline.project_id,
            ImportBatch.baseline_plan_id == baseline.id,
        )
    ) or 0
    latest_date = db.scalar(
        select(func.max(ImportBatch.data_date)).where(
            ImportBatch.project_id == baseline.project_id,
            ImportBatch.baseline_plan_id == baseline.id,
        )
    )
    return BaselinePlanRead.model_validate(baseline).model_copy(
        update={"bound_batch_count": count, "latest_bound_batch_date": latest_date}
    )


def _read_bound_batch(batch: ImportBatch, baseline_name: str | None) -> BaselineBoundBatch:
    return BaselineBoundBatch.model_validate(batch).model_copy(
        update={"baseline_plan_id": batch.baseline_plan_id, "baseline_plan_name": baseline_name}
    )
