from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.mapping_field import MappingField
from app.models.mapping_template import MappingTemplate
from app.models.project_template import ProjectTemplate
from app.schemas.mapping import FieldMapping
from app.schemas.template import MappingTemplateDetail, MappingTemplateUpdate, ProjectTemplateRead, ProjectTemplateUpdate
from app.services.project_template_service import copy_project_template

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("/project-templates", response_model=list[ProjectTemplateRead])
def list_project_templates(db: Session = Depends(get_db)) -> list[ProjectTemplate]:
    return list(db.scalars(select(ProjectTemplate).order_by(ProjectTemplate.is_builtin.desc(), ProjectTemplate.id.asc())).all())


@router.get("/project-templates/{template_id}", response_model=ProjectTemplateRead)
def get_project_template(template_id: int, db: Session = Depends(get_db)) -> ProjectTemplate:
    return _get_project_template(template_id, db)


@router.put("/project-templates/{template_id}", response_model=ProjectTemplateRead)
def update_project_template(template_id: int, payload: ProjectTemplateUpdate, db: Session = Depends(get_db)) -> ProjectTemplate:
    template = _get_project_template(template_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    db.commit()
    db.refresh(template)
    return template


@router.post("/project-templates/{template_id}/copy", response_model=ProjectTemplateRead, status_code=status.HTTP_201_CREATED)
def copy_builtin_project_template(template_id: int, db: Session = Depends(get_db)) -> ProjectTemplate:
    template = _get_project_template(template_id, db)
    copied = copy_project_template(db, template)
    db.commit()
    db.refresh(copied)
    return copied


@router.delete("/project-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_template(template_id: int, db: Session = Depends(get_db)) -> None:
    template = _get_project_template(template_id, db)
    if template.is_builtin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="内置项目模板不能删除，可以先复制后修改。")
    db.delete(template)
    db.commit()


@router.get("/mapping-templates", response_model=list[MappingTemplateDetail])
def list_mapping_templates(db: Session = Depends(get_db)) -> list[MappingTemplateDetail]:
    templates = list(db.scalars(select(MappingTemplate).order_by(MappingTemplate.updated_at.desc(), MappingTemplate.id.desc())).all())
    return [_mapping_template_detail(db, template) for template in templates]


@router.get("/mapping-templates/{template_id}", response_model=MappingTemplateDetail)
def get_mapping_template(template_id: int, db: Session = Depends(get_db)) -> MappingTemplateDetail:
    return _mapping_template_detail(db, _get_mapping_template(template_id, db))


@router.put("/mapping-templates/{template_id}", response_model=MappingTemplateDetail)
def update_mapping_template(template_id: int, payload: MappingTemplateUpdate, db: Session = Depends(get_db)) -> MappingTemplateDetail:
    template = _get_mapping_template(template_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    db.commit()
    db.refresh(template)
    return _mapping_template_detail(db, template)


@router.delete("/mapping-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mapping_template(template_id: int, db: Session = Depends(get_db)) -> None:
    template = _get_mapping_template(template_id, db)
    db.query(MappingField).filter(MappingField.template_id == template.id).delete()
    db.delete(template)
    db.commit()


def _get_project_template(template_id: int, db: Session) -> ProjectTemplate:
    template = db.get(ProjectTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目模板不存在。")
    return template


def _get_mapping_template(template_id: int, db: Session) -> MappingTemplate:
    template = db.get(MappingTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="字段映射模板不存在。")
    return template


def _mapping_template_detail(db: Session, template: MappingTemplate) -> MappingTemplateDetail:
    fields = list(
        db.scalars(
            select(MappingField)
            .where(MappingField.template_id == template.id)
            .order_by(MappingField.sort_order.asc(), MappingField.id.asc())
        )
    )
    return MappingTemplateDetail(
        id=template.id,
        project_id=template.project_id,
        name=template.name,
        description=template.description,
        project_type=template.project_type,
        is_global=template.is_global,
        is_active=template.is_active,
        last_used_at=template.last_used_at,
        use_count=template.use_count or 0,
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
        created_at=template.created_at,
        updated_at=template.updated_at,
    )
