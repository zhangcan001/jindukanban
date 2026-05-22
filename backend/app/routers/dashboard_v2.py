from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.project import Project
from app.schemas.analytics import DashboardV2Response
from app.services.dashboard_v2_service import build_dashboard_v2

router = APIRouter(prefix="/projects/{project_id}", tags=["dashboard-v2"])


def get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PROJECT_NOT_FOUND", "message": "当前项目不存在或已被清理。"},
        )
    return project


@router.get("/dashboard-v2", response_model=DashboardV2Response)
def dashboard_v2(
    project_id: int,
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
    status_filter: str | None = Query(default=None, alias="status"),
    calculation_profile_id: int | None = None,
    calculation_method: str | None = None,
    baseline_plan_id: int | None = None,
    db: Session = Depends(get_db),
) -> DashboardV2Response:
    project = get_project_or_404(project_id, db)
    return build_dashboard_v2(
        db,
        project,
        view_mode=view_mode,
        data_date=data_date,
        import_group_id=import_group_id,
        batch_id=batch_id,
        sheet_name=sheet_name,
        construction_unit=construction_unit,
        building=building,
        floor=floor,
        discipline=discipline,
        system_name=system_name,
        status=status_filter,
        calculation_profile_id=calculation_profile_id,
        calculation_method=calculation_method,
        baseline_plan_id=baseline_plan_id,
    )
