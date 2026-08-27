from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.auth import ActorContext
from app.domain.models import utc_now
from app.infrastructure.database import (
    DepartmentRecord,
    MembershipRecord,
    ProjectRecord,
    WorkItemRecord,
    get_session,
)
from app.infrastructure.sql_repositories import record_audit
from app.presentation.auth import current_actor


class ProjectInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=10_000)
    owner_id: UUID
    department_id: UUID | None = None
    starts_at: datetime | None = None
    due_at: datetime | None = None


class ProjectStatusInput(BaseModel):
    status: Literal["PLANNED", "ACTIVE", "ON_HOLD", "COMPLETED", "CANCELLED"]


class ProjectView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str
    status: str
    owner_id: UUID
    department_id: UUID | None
    starts_at: datetime | None
    due_at: datetime | None
    created_at: datetime


class ProjectDetail(ProjectView):
    work_items: int
    completed_work_items: int


class ProjectWorkInput(BaseModel):
    work_item_id: UUID


router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def project_for_actor(session: Session, actor: ActorContext, project_id: UUID) -> ProjectRecord:
    project = session.scalar(
        select(ProjectRecord).where(
            ProjectRecord.id == project_id,
            ProjectRecord.organization_id == actor.organization_id,
            ProjectRecord.archived_at.is_(None),
        )
    )
    if project is None:
        raise HTTPException(404, "Project not found")
    return project


@router.post("", response_model=ProjectView, status_code=201)
def create_project(
    payload: ProjectInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    actor.require("project.manage")
    owner = session.scalar(
        select(MembershipRecord.id).where(
            MembershipRecord.organization_id == actor.organization_id,
            MembershipRecord.user_id == payload.owner_id,
        )
    )
    if owner is None:
        raise HTTPException(404, "Project owner not found")
    if payload.department_id and not session.scalar(
        select(DepartmentRecord.id).where(
            DepartmentRecord.organization_id == actor.organization_id,
            DepartmentRecord.id == payload.department_id,
        )
    ):
        raise HTTPException(404, "Department not found")
    if payload.starts_at and payload.due_at and payload.due_at <= payload.starts_at:
        raise HTTPException(422, "Project deadline must be after its start")
    project = ProjectRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        status="PLANNED",
        owner_id=payload.owner_id,
        department_id=payload.department_id,
        starts_at=payload.starts_at,
        due_at=payload.due_at,
        created_at=utc_now(),
        archived_at=None,
    )
    session.add(project)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="project.create",
        entity_type="project",
        entity_id=project.id,
        new_state={"name": project.name, "status": project.status},
    )
    session.commit()
    return project


@router.get("", response_model=list[ProjectView])
def list_projects(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    actor.require("project.view")
    return session.scalars(
        select(ProjectRecord)
        .where(
            ProjectRecord.organization_id == actor.organization_id,
            ProjectRecord.archived_at.is_(None),
        )
        .order_by(ProjectRecord.created_at.desc())
    ).all()


@router.get("/{project_id}", response_model=ProjectDetail)
def project_detail(
    project_id: UUID,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> ProjectDetail:
    actor.require("project.view")
    project = project_for_actor(session, actor, project_id)
    total = (
        session.scalar(
            select(func.count())
            .select_from(WorkItemRecord)
            .where(
                WorkItemRecord.organization_id == actor.organization_id,
                WorkItemRecord.project_id == project.id,
            )
        )
        or 0
    )
    completed = (
        session.scalar(
            select(func.count())
            .select_from(WorkItemRecord)
            .where(
                WorkItemRecord.organization_id == actor.organization_id,
                WorkItemRecord.project_id == project.id,
                WorkItemRecord.status.in_(["COMPLETED", "DONE"]),
            )
        )
        or 0
    )
    data = ProjectView.model_validate(project).model_dump()
    return ProjectDetail(**data, work_items=total, completed_work_items=completed)


@router.post("/{project_id}/work-items", status_code=204)
def add_project_work(
    project_id: UUID,
    payload: ProjectWorkInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    actor.require("project.manage")
    project = project_for_actor(session, actor, project_id)
    item = session.scalar(
        select(WorkItemRecord).where(
            WorkItemRecord.id == payload.work_item_id,
            WorkItemRecord.organization_id == actor.organization_id,
        )
    )
    if item is None:
        raise HTTPException(404, "Work item not found")
    item.project_id = project.id
    session.commit()


@router.patch("/{project_id}/status", response_model=ProjectView)
def update_project_status(
    project_id: UUID,
    payload: ProjectStatusInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    actor.require("project.manage")
    project = project_for_actor(session, actor, project_id)
    project.status = payload.status
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="project.status",
        entity_type="project",
        entity_id=project.id,
        new_state={"status": project.status},
    )
    session.commit()
    return project
