from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.auth import ActorContext
from app.infrastructure.database import (
    AuditEventRecord,
    DepartmentRecord,
    PermissionRecord,
    RoleRecord,
    TeamRecord,
    get_session,
)
from app.infrastructure.sql_repositories import record_audit
from app.presentation.auth import current_actor


class TeamInput(BaseModel):
    department_id: UUID
    name: str = Field(min_length=2, max_length=120)


class TeamView(TeamInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    archived_at: datetime | None


class RoleInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=240)
    permissions: list[str] = Field(default_factory=list)


class RoleView(BaseModel):
    id: UUID
    name: str
    description: str
    permissions: list[str]


class AuditView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    actor_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID
    new_state: dict[str, object]
    created_at: datetime


router = APIRouter(prefix="/api/v1")


@router.post("/teams", response_model=TeamView, status_code=201)
def create_team(
    payload: TeamInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    actor.require("department.manage")
    department = session.scalar(
        select(DepartmentRecord).where(
            DepartmentRecord.id == payload.department_id,
            DepartmentRecord.organization_id == actor.organization_id,
            DepartmentRecord.archived_at.is_(None),
        )
    )
    if department is None:
        raise HTTPException(404, "Department not found")
    team = TeamRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        department_id=department.id,
        name=payload.name.strip(),
        archived_at=None,
    )
    session.add(team)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="team.create",
        entity_type="team",
        entity_id=team.id,
        new_state={"name": team.name, "department_id": str(department.id)},
    )
    session.commit()
    return team


@router.get("/teams", response_model=list[TeamView])
def list_teams(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    actor.require("department.manage")
    return session.scalars(
        select(TeamRecord).where(
            TeamRecord.organization_id == actor.organization_id,
            TeamRecord.archived_at.is_(None),
        )
    ).all()


@router.delete("/teams/{team_id}", status_code=204)
def archive_team(
    team_id: UUID,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    actor.require("department.manage")
    team = session.scalar(
        select(TeamRecord).where(
            TeamRecord.id == team_id, TeamRecord.organization_id == actor.organization_id
        )
    )
    if team is None:
        raise HTTPException(404, "Team not found")
    team.archived_at = datetime.now(UTC)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="team.archive",
        entity_type="team",
        entity_id=team.id,
        new_state={"archived": True},
    )
    session.commit()
    return Response(status_code=204)


@router.post("/roles", response_model=RoleView, status_code=201)
def create_role(
    payload: RoleInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> RoleView:
    actor.require("role.manage")
    permissions: list[PermissionRecord] = []
    for code in sorted(set(payload.permissions)):
        permission = session.scalar(select(PermissionRecord).where(PermissionRecord.code == code))
        if permission is None:
            permission = PermissionRecord(id=uuid4(), code=code, description="")
            session.add(permission)
        permissions.append(permission)
    role = RoleRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        permissions=permissions,
    )
    session.add(role)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="role.create",
        entity_type="role",
        entity_id=role.id,
        new_state={"name": role.name, "permissions": payload.permissions},
    )
    session.commit()
    return RoleView(
        id=role.id,
        name=role.name,
        description=role.description,
        permissions=[item.code for item in role.permissions],
    )


@router.get("/roles", response_model=list[RoleView])
def list_roles(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> list[RoleView]:
    actor.require("role.manage")
    roles = session.scalars(
        select(RoleRecord).where(RoleRecord.organization_id == actor.organization_id)
    ).all()
    return [
        RoleView(
            id=role.id,
            name=role.name,
            description=role.description,
            permissions=[permission.code for permission in role.permissions],
        )
        for role in roles
    ]


@router.get("/audit", response_model=list[AuditView])
def list_audit(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
    limit: int = 100,
) -> object:
    actor.require("audit.view")
    safe_limit = min(max(limit, 1), 500)
    return session.scalars(
        select(AuditEventRecord)
        .where(AuditEventRecord.organization_id == actor.organization_id)
        .order_by(AuditEventRecord.created_at.desc())
        .limit(safe_limit)
    ).all()
