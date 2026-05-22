from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.calculation_profile import CalculationProfile
from app.models.project import Project
from app.schemas.calculation_profile import (
    CalculationProfileCreate,
    CalculationProfileRead,
    CalculationProfileUpdate,
)

router = APIRouter(prefix="/projects/{project_id}/calculation-profiles", tags=["calculation profiles"])


def get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前项目不存在或已被清理。")
    return project


def get_profile_or_404(project_id: int, profile_id: int, db: Session) -> CalculationProfile:
    profile = db.get(CalculationProfile, profile_id)
    if profile is None or profile.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calculation profile not found")
    return profile


def apply_default_profile(project: Project, profile: CalculationProfile, db: Session) -> None:
    statement = select(CalculationProfile).where(CalculationProfile.project_id == project.id)
    for item in db.scalars(statement):
        item.is_default = item.id == profile.id
    project.default_calculation_profile_id = profile.id


@router.get("", response_model=list[CalculationProfileRead])
def list_calculation_profiles(project_id: int, db: Session = Depends(get_db)) -> list[CalculationProfile]:
    get_project_or_404(project_id, db)
    statement = (
        select(CalculationProfile)
        .where(CalculationProfile.project_id == project_id)
        .order_by(CalculationProfile.is_default.desc(), CalculationProfile.id.desc())
    )
    return list(db.scalars(statement).all())


@router.post("", response_model=CalculationProfileRead, status_code=status.HTTP_201_CREATED)
def create_calculation_profile(
    project_id: int,
    payload: CalculationProfileCreate,
    db: Session = Depends(get_db),
) -> CalculationProfile:
    project = get_project_or_404(project_id, db)
    profile = CalculationProfile(project_id=project_id, **payload.model_dump())
    db.add(profile)
    db.flush()

    has_default = project.default_calculation_profile_id is not None
    if payload.is_default or not has_default:
        apply_default_profile(project, profile, db)

    db.commit()
    db.refresh(profile)
    return profile


@router.get("/{profile_id}", response_model=CalculationProfileRead)
def get_calculation_profile(
    project_id: int,
    profile_id: int,
    db: Session = Depends(get_db),
) -> CalculationProfile:
    get_project_or_404(project_id, db)
    return get_profile_or_404(project_id, profile_id, db)


@router.put("/{profile_id}", response_model=CalculationProfileRead)
def update_calculation_profile(
    project_id: int,
    profile_id: int,
    payload: CalculationProfileUpdate,
    db: Session = Depends(get_db),
) -> CalculationProfile:
    project = get_project_or_404(project_id, db)
    profile = get_profile_or_404(project_id, profile_id, db)
    update_data = payload.model_dump(exclude_unset=True)
    requested_default = update_data.pop("is_default", None)
    for field, value in update_data.items():
        setattr(profile, field, value)

    if requested_default is True:
        apply_default_profile(project, profile, db)
    elif requested_default is False and project.default_calculation_profile_id == profile.id:
        project.default_calculation_profile_id = None
        profile.is_default = False

    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_calculation_profile(
    project_id: int,
    profile_id: int,
    db: Session = Depends(get_db),
) -> None:
    project = get_project_or_404(project_id, db)
    profile = get_profile_or_404(project_id, profile_id, db)
    if project.default_calculation_profile_id == profile.id:
        project.default_calculation_profile_id = None
    db.delete(profile)
    db.commit()

