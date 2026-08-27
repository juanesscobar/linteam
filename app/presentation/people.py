from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.auth import ActorContext
from app.infrastructure.database import (
    ApprovalRequestRecord,
    DepartmentRecord,
    MembershipRecord,
    NotificationPreferenceRecord,
    TeamRecord,
    UserRecord,
    WorkItemRecord,
    get_session,
)
from app.infrastructure.sql_repositories import record_audit
from app.presentation.auth import current_actor


class ProfileUpdate(BaseModel):
    job_title: str = Field(default="", max_length=120)
    department_id: UUID | None = None
    team_id: UUID | None = None
    supervisor_id: UUID | None = None
    phone: str = Field(default="", max_length=40)
    whatsapp_id: str = Field(default="", max_length=120)
    telegram_id: str = Field(default="", max_length=120)
    timezone: str = Field(default="America/Asuncion", max_length=60)
    work_schedule: dict[str, object] = Field(default_factory=dict)
    location: str = Field(default="", max_length=160)
    responsibilities: list[str] = Field(default_factory=list, max_length=100)
    specialties: list[str] = Field(default_factory=list, max_length=100)


class ProfileView(ProfileUpdate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    organization_id: UUID
    name: str
    email: str
    active: bool
    permissions: list[str]
    roles: list[str]
    operational: dict[str, int]


class PreferenceInput(BaseModel):
    event_type: str = Field(min_length=2, max_length=80)
    channels: list[str] = Field(min_length=1, max_length=5)
    digest: str = Field(default="IMMEDIATE", pattern="^(IMMEDIATE|DAILY|WEEKLY)$")
    enabled: bool = True


router = APIRouter(prefix="/api/v1")


def _membership(session: Session, actor: ActorContext, member_id: UUID) -> MembershipRecord:
    value = session.scalar(
        select(MembershipRecord).where(
            MembershipRecord.id == member_id,
            MembershipRecord.organization_id == actor.organization_id,
        )
    )
    if value is None:
        raise HTTPException(404, "Member not found")
    return value


def _profile(session: Session, actor: ActorContext, member: MembershipRecord) -> ProfileView:
    user = session.get(UserRecord, member.user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    now = datetime.now(UTC)
    active = (
        session.scalar(
            select(func.count())
            .select_from(WorkItemRecord)
            .where(
                WorkItemRecord.organization_id == actor.organization_id,
                WorkItemRecord.assigned_to == member.user_id,
                WorkItemRecord.status.notin_(["COMPLETED", "CANCELLED", "ARCHIVED"]),
            )
        )
        or 0
    )
    overdue = (
        session.scalar(
            select(func.count())
            .select_from(WorkItemRecord)
            .where(
                WorkItemRecord.organization_id == actor.organization_id,
                WorkItemRecord.assigned_to == member.user_id,
                WorkItemRecord.due_at < now,
                WorkItemRecord.status.notin_(["COMPLETED", "CANCELLED", "ARCHIVED"]),
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
                WorkItemRecord.assigned_to == member.user_id,
                WorkItemRecord.status == "COMPLETED",
            )
        )
        or 0
    )
    created = (
        session.scalar(
            select(func.count())
            .select_from(WorkItemRecord)
            .where(
                WorkItemRecord.organization_id == actor.organization_id,
                WorkItemRecord.created_by == member.user_id,
            )
        )
        or 0
    )
    approvals = (
        session.scalar(
            select(func.count())
            .select_from(ApprovalRequestRecord)
            .where(
                ApprovalRequestRecord.organization_id == actor.organization_id,
                ApprovalRequestRecord.requested_from == member.user_id,
                ApprovalRequestRecord.status == "PENDING",
            )
        )
        or 0
    )
    return ProfileView(
        id=member.id,
        user_id=member.user_id,
        organization_id=member.organization_id,
        name=user.name,
        email=user.email,
        active=user.is_active,
        permissions=member.permissions,
        roles=[role.name for role in member.roles],
        operational={
            "active_assignments": active,
            "overdue": overdue,
            "completed": completed,
            "created": created,
            "pending_approvals": approvals,
            "workload": active,
        },
        **{name: getattr(member, name) for name in ProfileUpdate.model_fields},
    )


@router.get("/members", response_model=list[ProfileView])
def list_members(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> list[ProfileView]:
    actor.require("member.manage")
    members = session.scalars(
        select(MembershipRecord).where(MembershipRecord.organization_id == actor.organization_id)
    ).all()
    return [_profile(session, actor, member) for member in members]


@router.get("/members/{member_id}", response_model=ProfileView)
def get_profile(
    member_id: UUID,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> ProfileView:
    member = _membership(session, actor, member_id)
    if member.user_id != actor.user_id:
        actor.require("member.manage")
    return _profile(session, actor, member)


@router.put("/members/{member_id}", response_model=ProfileView)
def update_profile(
    member_id: UUID,
    payload: ProfileUpdate,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> ProfileView:
    actor.require("member.manage")
    member = _membership(session, actor, member_id)
    if payload.department_id is not None:
        department = session.scalar(
            select(DepartmentRecord).where(
                DepartmentRecord.id == payload.department_id,
                DepartmentRecord.organization_id == actor.organization_id,
            )
        )
        if department is None:
            raise HTTPException(404, "Department not found")
    if payload.team_id is not None:
        team = session.scalar(
            select(TeamRecord).where(
                TeamRecord.id == payload.team_id,
                TeamRecord.organization_id == actor.organization_id,
                TeamRecord.department_id == payload.department_id,
            )
        )
        if team is None:
            raise HTTPException(422, "Team does not belong to the selected department")
    if payload.supervisor_id is not None:
        supervisor = session.scalar(
            select(MembershipRecord).where(
                MembershipRecord.user_id == payload.supervisor_id,
                MembershipRecord.organization_id == actor.organization_id,
            )
        )
        if supervisor is None or supervisor.user_id == member.user_id:
            raise HTTPException(422, "Invalid supervisor")
    previous = {"department_id": str(member.department_id), "team_id": str(member.team_id)}
    for name, value in payload.model_dump().items():
        setattr(member, name, value)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="member.update",
        entity_type="membership",
        entity_id=member.id,
        new_state={"previous": previous, **payload.model_dump(mode="json")},
    )
    session.commit()
    return _profile(session, actor, member)


@router.put("/me/notification-preferences", status_code=204)
def set_notification_preference(
    payload: PreferenceInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    allowed = {"IN_APP", "PUSH", "EMAIL", "WHATSAPP", "TELEGRAM"}
    channels = set(payload.channels)
    if not channels <= allowed:
        raise HTTPException(422, "Unsupported notification channel")
    for channel in channels:
        value = session.scalar(
            select(NotificationPreferenceRecord).where(
                NotificationPreferenceRecord.organization_id == actor.organization_id,
                NotificationPreferenceRecord.user_id == actor.user_id,
                NotificationPreferenceRecord.channel == channel,
            )
        )
        if value is None:
            value = NotificationPreferenceRecord(
                id=uuid4(),
                organization_id=actor.organization_id,
                user_id=actor.user_id,
                channel=channel,
            )
            session.add(value)
        value.enabled = payload.enabled
        value.quiet_hours = {"event_type": payload.event_type, "digest": payload.digest}
    session.commit()
