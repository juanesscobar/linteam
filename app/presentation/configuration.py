from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.auth import ActorContext
from app.infrastructure.database import (
    BusinessUnitRecord,
    CustomFieldDefinitionRecord,
    TagRecord,
    WorkItemTypeRecord,
    get_session,
)
from app.infrastructure.sql_repositories import record_audit
from app.presentation.auth import current_actor


class BusinessUnitInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=2000)


class BusinessUnitView(BusinessUnitInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    archived_at: datetime | None


class WorkItemTypeInput(BaseModel):
    code: str = Field(pattern="^[A-Z][A-Z0-9_]{1,79}$")
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=500)
    form_schema: dict[str, object] = Field(default_factory=dict)


class TagInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str = Field(default="#65736c", pattern="^#[0-9a-fA-F]{6}$")


class CustomFieldInput(BaseModel):
    key: str = Field(pattern="^[a-z][a-z0-9_]{1,79}$")
    name: str = Field(min_length=2, max_length=120)
    field_type: Literal["TEXT", "NUMBER", "BOOLEAN", "DATE", "SELECT"]
    required: bool = False
    options: list[object] = Field(default_factory=list, max_length=100)


router = APIRouter(prefix="/api/v1/configuration", tags=["configuration"])


@router.post("/business-units", response_model=BusinessUnitView, status_code=201)
def create_business_unit(
    payload: BusinessUnitInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    actor.require("department.manage")
    value = BusinessUnitRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        archived_at=None,
    )
    session.add(value)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="business_unit.create",
        entity_type="business_unit",
        entity_id=value.id,
        new_state={"name": value.name},
    )
    session.commit()
    return value


@router.get("/business-units", response_model=list[BusinessUnitView])
def list_business_units(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    actor.require("department.manage")
    return session.scalars(
        select(BusinessUnitRecord)
        .where(
            BusinessUnitRecord.organization_id == actor.organization_id,
            BusinessUnitRecord.archived_at.is_(None),
        )
        .order_by(BusinessUnitRecord.name)
    ).all()


@router.post("/work-item-types", status_code=201)
def create_work_item_type(
    payload: WorkItemTypeInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("workflow.manage")
    value = WorkItemTypeRecord(
        id=uuid4(), organization_id=actor.organization_id, active=True, **payload.model_dump()
    )
    session.add(value)
    session.commit()
    return {"id": value.id, "code": value.code, "name": value.name, "active": True}


@router.get("/work-item-types")
def list_work_item_types(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> list[dict[str, object]]:
    actor.require("workitem.view")
    values = session.scalars(
        select(WorkItemTypeRecord)
        .where(
            WorkItemTypeRecord.organization_id == actor.organization_id,
            WorkItemTypeRecord.active.is_(True),
        )
        .order_by(WorkItemTypeRecord.name)
    ).all()
    return [
        {"id": value.id, "code": value.code, "name": value.name, "form_schema": value.form_schema}
        for value in values
    ]


@router.post("/tags", status_code=201)
def create_tag(
    payload: TagInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("workflow.manage")
    value = TagRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        name=payload.name.strip(),
        color=payload.color,
    )
    session.add(value)
    session.commit()
    return {"id": value.id, "name": value.name, "color": value.color}


@router.post("/custom-fields", status_code=201)
def create_custom_field(
    payload: CustomFieldInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("workflow.manage")
    if payload.field_type == "SELECT" and not payload.options:
        raise HTTPException(422, "SELECT fields require options")
    value = CustomFieldDefinitionRecord(
        id=uuid4(), organization_id=actor.organization_id, active=True, **payload.model_dump()
    )
    session.add(value)
    session.commit()
    return {"id": value.id, "key": value.key, "field_type": value.field_type, "active": True}
