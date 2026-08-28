import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.auth import ActorContext
from app.application.use_cases import CreateWorkItem, ListWorkItems
from app.domain.models import Priority, WorkItemStatus
from app.infrastructure.database import (
    CustomFieldDefinitionRecord,
    CustomFieldValueRecord,
    AssignmentRecord,
    DepartmentRecord,
    ExpectedDeliverableRecord,
    MembershipRecord,
    NotificationRecord,
    OrganizationRecord,
    OrganizationInviteRecord,
    RoleRecord,
    TagRecord,
    TeamRecord,
    UserRecord,
    WorkItemRecord,
    WorkItemTypeRecord,
    get_session,
)
from app.infrastructure.security import hash_password
from app.infrastructure.sql_repositories import (
    SqlOrganizationRepository,
    SqlWorkItemRepository,
    record_audit,
    record_event,
)
from app.presentation.auth import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    authenticate,
    current_actor,
    issue_token_pair,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.settings import Settings, get_settings


class BootstrapRequest(BaseModel):
    organization_name: str = Field(min_length=2, max_length=120)
    organization_code: str = Field(default="LINTEAM", min_length=2, max_length=30)
    admin_name: str = Field(min_length=2, max_length=160)
    admin_email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class OrganizationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    code: str
    created_at: datetime


class InvitationInput(BaseModel):
    email: EmailStr
    expires_in_days: int = Field(default=7, ge=1, le=30)


class InvitationView(BaseModel):
    id: UUID
    email: EmailStr
    organization_code: str
    invitation_token: str
    expires_at: datetime


class JoinRequest(BaseModel):
    organization_code: str = Field(min_length=2, max_length=30)
    invitation_token: str = Field(min_length=20, max_length=200)
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class DepartmentInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=2000)


class DepartmentView(DepartmentInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    archived_at: datetime | None


class MemberInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    department_id: UUID | None = None
    team_id: UUID | None = None
    job_title: str = Field(default="", max_length=120)
    permissions: list[str] = Field(default_factory=list)
    role_ids: list[UUID] = Field(default_factory=list)


class WorkItemInput(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=20_000)
    type_code: str = Field(min_length=1, max_length=80)
    priority: Priority = Priority.NORMAL
    impact: str = Field(default="INDIVIDUAL", max_length=30)
    urgency: str = Field(default="NORMAL", max_length=20)
    category: str = Field(default="", max_length=120)
    source_department_id: UUID | None = None
    destination_department_id: UUID | None = None
    branch: str = Field(default="", max_length=160)
    expected_deliverable: str = Field(default="", max_length=500)
    tag_ids: list[UUID] = Field(default_factory=list)
    custom_fields: dict[str, object] = Field(default_factory=dict)
    assignee_ids: list[UUID] = Field(default_factory=list, max_length=50)
    due_at: datetime | None = None


class WorkItemView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    human_readable_id: str
    organization_id: UUID
    title: str
    description: str
    type_code: str
    priority: Priority
    status: str
    created_by: UUID
    assigned_to: UUID | None
    due_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AssigneeView(BaseModel):
    id: UUID
    name: str
    email: EmailStr


router = APIRouter(prefix="/api/v1")
DEFAULT_MEMBER_PERMISSIONS = ["workitem.view", "workitem.create", "workitem.update"]


@router.post("/setup", response_model=OrganizationView, status_code=201)
def bootstrap(
    payload: BootstrapRequest,
    x_bootstrap_token: Annotated[str, Header()],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> object:
    if x_bootstrap_token != settings.bootstrap_token:
        raise HTTPException(403, "Invalid bootstrap token")
    if session.scalar(select(func.count()).select_from(OrganizationRecord)):
        raise HTTPException(409, "System is already initialized")
    organization = OrganizationRecord(
        id=uuid4(),
        name=payload.organization_name.strip(),
        code=payload.organization_code.strip().upper(),
        created_at=datetime.now(UTC),
    )
    user = UserRecord(
        id=uuid4(),
        email=str(payload.admin_email).lower(),
        name=payload.admin_name.strip(),
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    session.add_all([organization, user])
    session.flush()
    session.add(
        MembershipRecord(
            id=uuid4(),
            organization_id=organization.id,
            user_id=user.id,
            department_id=None,
            job_title="Administrator",
            permissions=["*"],
        )
    )
    record_audit(
        session,
        organization_id=organization.id,
        actor_id=user.id,
        action="organization.bootstrap",
        entity_type="organization",
        entity_id=organization.id,
        new_state={"name": organization.name},
    )
    session.commit()
    return organization


@router.post("/invitations", response_model=InvitationView, status_code=201)
def create_invitation(
    payload: InvitationInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> InvitationView:
    actor.require("member.manage")
    organization = session.get(OrganizationRecord, actor.organization_id)
    if organization is None:
        raise HTTPException(404, "Organization not found")
    email = str(payload.email).lower()
    if session.scalar(select(UserRecord).where(UserRecord.email == email)) is not None:
        raise HTTPException(409, "This email already has an account")
    raw_token = secrets.token_urlsafe(32)
    invitation = OrganizationInviteRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        email=email,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        created_by=actor.user_id,
        expires_at=datetime.now(UTC) + timedelta(days=payload.expires_in_days),
        accepted_at=None,
        created_at=datetime.now(UTC),
    )
    session.add(invitation)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="invitation.create",
        entity_type="organization_invite",
        entity_id=invitation.id,
        new_state={"email": email, "expires_at": invitation.expires_at.isoformat()},
    )
    session.commit()
    return InvitationView(
        id=invitation.id,
        email=email,
        organization_code=organization.code,
        invitation_token=raw_token,
        expires_at=invitation.expires_at,
    )


@router.post("/auth/join", response_model=TokenResponse, status_code=201)
def join_organization(
    payload: JoinRequest,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    email = str(payload.email).lower()
    organization = session.scalar(
        select(OrganizationRecord).where(OrganizationRecord.code == payload.organization_code.strip().upper())
    )
    if organization is None:
        raise HTTPException(404, "Organization code not found")
    token_hash = hashlib.sha256(payload.invitation_token.encode()).hexdigest()
    invitation = session.scalar(
        select(OrganizationInviteRecord).where(
            OrganizationInviteRecord.organization_id == organization.id,
            OrganizationInviteRecord.email == email,
            OrganizationInviteRecord.token_hash == token_hash,
        )
    )
    now = datetime.now(UTC)
    invitation_expired = invitation is None or invitation.expires_at.replace(tzinfo=UTC) <= now
    if invitation_expired or invitation.accepted_at is not None:
        raise HTTPException(403, "Invitation is invalid, expired, or already used")
    if not hmac.compare_digest(invitation.token_hash, token_hash):
        raise HTTPException(403, "Invitation is invalid, expired, or already used")
    if session.scalar(select(UserRecord).where(UserRecord.email == email)) is not None:
        raise HTTPException(409, "This email already has an account")
    user = UserRecord(
        id=uuid4(),
        email=email,
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    session.add(user)
    session.flush()
    membership = MembershipRecord(
        id=uuid4(),
        organization_id=organization.id,
        user_id=user.id,
        department_id=None,
        permissions=DEFAULT_MEMBER_PERMISSIONS,
    )
    session.add(membership)
    invitation.accepted_at = now
    record_audit(
        session,
        organization_id=organization.id,
        actor_id=user.id,
        action="member.join",
        entity_type="membership",
        entity_id=membership.id,
        new_state={"email": email},
    )
    response, _ = issue_token_pair(user.id, organization.id, session, settings)
    session.commit()
    return response


@router.post("/auth/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    return authenticate(payload, session, settings)


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh(
    payload: RefreshRequest,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    return rotate_refresh_token(payload, session, settings)


@router.post("/auth/logout", status_code=204)
def logout(
    payload: RefreshRequest,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    revoke_refresh_token(payload, session, settings)


@router.get("/departments", response_model=list[DepartmentView])
def list_departments(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    actor.require("department.manage")
    return session.scalars(
        select(DepartmentRecord)
        .where(
            DepartmentRecord.organization_id == actor.organization_id,
            DepartmentRecord.archived_at.is_(None),
        )
        .order_by(DepartmentRecord.name)
    ).all()


@router.post("/departments", response_model=DepartmentView, status_code=201)
def create_department(
    payload: DepartmentInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    actor.require("department.manage")
    department = DepartmentRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        archived_at=None,
    )
    session.add(department)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="department.create",
        entity_type="department",
        entity_id=department.id,
        new_state={"name": department.name},
    )
    session.commit()
    return department


@router.post("/members", status_code=201)
def create_member(
    payload: MemberInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("member.manage")
    if payload.department_id and not session.scalar(
        select(DepartmentRecord.id).where(
            DepartmentRecord.id == payload.department_id,
            DepartmentRecord.organization_id == actor.organization_id,
        )
    ):
        raise HTTPException(404, "Department not found")
    if payload.team_id:
        team = session.scalar(
            select(TeamRecord).where(
                TeamRecord.id == payload.team_id,
                TeamRecord.organization_id == actor.organization_id,
                TeamRecord.archived_at.is_(None),
            )
        )
        if team is None or team.department_id != payload.department_id:
            raise HTTPException(404, "Team not found in selected department")
    roles = session.scalars(
        select(RoleRecord).where(
            RoleRecord.id.in_(payload.role_ids),
            RoleRecord.organization_id == actor.organization_id,
        )
    ).all()
    if len(roles) != len(set(payload.role_ids)):
        raise HTTPException(404, "Role not found")
    if session.scalar(select(UserRecord.id).where(UserRecord.email == str(payload.email).lower())):
        raise HTTPException(409, "Email already registered")
    user = UserRecord(
        id=uuid4(),
        email=str(payload.email).lower(),
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    membership = MembershipRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        user_id=user.id,
        department_id=payload.department_id,
        team_id=payload.team_id,
        job_title=payload.job_title.strip(),
        permissions=payload.permissions,
        roles=list(roles),
    )
    session.add_all([user, membership])
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="member.create",
        entity_type="membership",
        entity_id=membership.id,
        new_state={"user_id": str(user.id), "email": user.email},
    )
    session.commit()
    return {"id": membership.id, "user_id": user.id, "email": user.email, "name": user.name}


@router.post("/work-items", response_model=WorkItemView, status_code=201)
def create_work_item(
    payload: WorkItemInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    core_fields = payload.model_dump(
        include={"title", "description", "type_code", "priority", "due_at"}
    )
    item = CreateWorkItem(
        SqlOrganizationRepository(session), SqlWorkItemRepository(session)
    ).execute(actor, **core_fields)
    record = session.get(WorkItemRecord, item.id)
    if record is None:
        raise HTTPException(500, "Work item persistence failed")
    department_ids = {
        value
        for value in (payload.source_department_id, payload.destination_department_id)
        if value is not None
    }
    if department_ids:
        valid_departments = set(
            session.scalars(
                select(DepartmentRecord.id).where(
                    DepartmentRecord.organization_id == actor.organization_id,
                    DepartmentRecord.id.in_(department_ids),
                    DepartmentRecord.archived_at.is_(None),
                )
            ).all()
        )
        if valid_departments != department_ids:
            raise HTTPException(404, "Department not found")
    work_type = session.scalar(
        select(WorkItemTypeRecord).where(
            WorkItemTypeRecord.organization_id == actor.organization_id,
            WorkItemTypeRecord.code == payload.type_code.upper(),
            WorkItemTypeRecord.active.is_(True),
        )
    )
    tags = session.scalars(
        select(TagRecord).where(
            TagRecord.organization_id == actor.organization_id,
            TagRecord.id.in_(payload.tag_ids),
        )
    ).all()
    if len(tags) != len(set(payload.tag_ids)):
        raise HTTPException(404, "Tag not found")
    definitions = session.scalars(
        select(CustomFieldDefinitionRecord).where(
            CustomFieldDefinitionRecord.organization_id == actor.organization_id,
            CustomFieldDefinitionRecord.active.is_(True),
        )
    ).all()
    by_key = {definition.key: definition for definition in definitions}
    unknown = set(payload.custom_fields) - set(by_key)
    missing = {definition.key for definition in definitions if definition.required} - set(
        payload.custom_fields
    )
    if unknown or missing:
        raise HTTPException(
            422, {"unknown_custom_fields": sorted(unknown), "missing": sorted(missing)}
        )
    record.type_id = work_type.id if work_type else None
    record.impact, record.urgency, record.category = (
        payload.impact,
        payload.urgency,
        payload.category,
    )
    record.source_department_id = payload.source_department_id
    record.destination_department_id = payload.destination_department_id
    record.branch, record.expected_deliverable = payload.branch, payload.expected_deliverable
    record.tags = list(tags)
    if payload.expected_deliverable:
        session.add(
            ExpectedDeliverableRecord(
                id=uuid4(),
                organization_id=actor.organization_id,
                work_item_id=item.id,
                kind="CUSTOM",
                description=payload.expected_deliverable,
                required=True,
                status="PENDING",
                created_at=datetime.now(UTC),
            )
        )
    session.add_all(
        [
            CustomFieldValueRecord(
                id=uuid4(),
                organization_id=actor.organization_id,
                work_item_id=item.id,
                definition_id=by_key[key].id,
                value=value,
            )
            for key, value in payload.custom_fields.items()
        ]
    )
    assignee_ids = list(dict.fromkeys(payload.assignee_ids))
    if assignee_ids:
        actor.require("workitem.assign")
        valid_assignee_ids = set(
            session.scalars(
                select(MembershipRecord.user_id).where(
                    MembershipRecord.organization_id == actor.organization_id,
                    MembershipRecord.user_id.in_(assignee_ids),
                )
            ).all()
        )
        if valid_assignee_ids != set(assignee_ids):
            raise HTTPException(404, "Assignee not found")
        now = datetime.now(UTC)
        record.assigned_to = assignee_ids[0]
        record.status = WorkItemStatus.ASSIGNED.value
        record.updated_at = now
        session.add_all(
            [
                AssignmentRecord(
                    id=uuid4(),
                    organization_id=actor.organization_id,
                    work_item_id=record.id,
                    assignee_id=assignee_id,
                    assigned_by=actor.user_id,
                    accepted_at=None,
                    created_at=now,
                )
                for assignee_id in assignee_ids
            ]
        )
        session.add_all(
            [
                NotificationRecord(
                    id=uuid4(),
                    organization_id=actor.organization_id,
                    recipient_id=assignee_id,
                    kind="ASSIGNMENT",
                    title=f"Asignación {record.human_readable_id}",
                    body=record.title,
                    entity_type="work_item",
                    entity_id=record.id,
                    read_at=None,
                    created_at=now,
                )
                for assignee_id in assignee_ids
            ]
        )
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="workitem.create",
        entity_type="work_item",
        entity_id=item.id,
        new_state={
            "title": item.title,
            "status": record.status,
            "assignee_ids": [str(assignee_id) for assignee_id in assignee_ids],
        },
    )
    record_event(
        session,
        organization_id=actor.organization_id,
        aggregate_type="work_item",
        aggregate_id=item.id,
        event_type="WorkItemCreated",
        payload={
            "reference": item.human_readable_id,
            "type": item.type_code,
            "assignee_ids": [str(assignee_id) for assignee_id in assignee_ids],
        },
    )
    session.commit()
    return item


@router.get("/work-item-assignees", response_model=list[AssigneeView])
def work_item_assignees(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> list[AssigneeView]:
    actor.require("workitem.assign")
    rows = session.execute(
        select(UserRecord.id, UserRecord.name, UserRecord.email)
        .join(MembershipRecord, MembershipRecord.user_id == UserRecord.id)
        .where(MembershipRecord.organization_id == actor.organization_id, UserRecord.is_active.is_(True))
        .order_by(UserRecord.name)
    ).all()
    return [AssigneeView(id=row.id, name=row.name, email=row.email) for row in rows]


@router.get("/work-items", response_model=list[WorkItemView])
def list_work_items(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    return ListWorkItems(SqlWorkItemRepository(session)).execute(actor)


@router.delete("/work-items/{work_item_id}", status_code=204)
def archive_work_item(
    work_item_id: UUID,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    """Remove a work item from active views while retaining the audit trail."""
    actor.require("workitem.delete")
    item = session.scalar(
        select(WorkItemRecord).where(
            WorkItemRecord.id == work_item_id,
            WorkItemRecord.organization_id == actor.organization_id,
        )
    )
    if item is None:
        raise HTTPException(404, "Work item not found")
    item.status = WorkItemStatus.ARCHIVED.value
    item.updated_at = datetime.now(UTC)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="workitem.archive",
        entity_type="work_item",
        entity_id=item.id,
        new_state={"status": item.status},
    )
    session.commit()
