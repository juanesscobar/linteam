from collections.abc import Generator
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from app.settings import get_settings


class Base(DeclarativeBase):
    pass


class OrganizationRecord(Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    departments: Mapped[list["DepartmentRecord"]] = relationship(back_populates="organization")


class BusinessUnitRecord(Base):
    __tablename__ = "business_units"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DepartmentRecord(Base):
    __tablename__ = "departments"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    business_unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("business_units.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    organization: Mapped[OrganizationRecord] = relationship(back_populates="departments")


class TeamRecord(Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    department_id: Mapped[UUID] = mapped_column(ForeignKey("departments.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)


class RefreshSessionRecord(Base):
    __tablename__ = "refresh_sessions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MembershipRecord(Base):
    __tablename__ = "memberships"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    team_id: Mapped[UUID | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    job_title: Mapped[str] = mapped_column(String(120), default="")
    supervisor_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    phone: Mapped[str] = mapped_column(String(40), default="")
    whatsapp_id: Mapped[str] = mapped_column(String(120), default="")
    telegram_id: Mapped[str] = mapped_column(String(120), default="")
    timezone: Mapped[str] = mapped_column(String(60), default="America/Asuncion")
    work_schedule: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    location: Mapped[str] = mapped_column(String(160), default="")
    responsibilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    specialties: Mapped[list[str]] = mapped_column(JSON, default=list)
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list)
    roles: Mapped[list["RoleRecord"]] = relationship(
        secondary=lambda: membership_roles, lazy="selectin"
    )


role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

work_item_tags = Table(
    "work_item_tags",
    Base.metadata,
    Column("work_item_id", ForeignKey("work_items.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

membership_roles = Table(
    "membership_roles",
    Base.metadata,
    Column("membership_id", ForeignKey("memberships.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class PermissionRecord(Base):
    __tablename__ = "permissions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(String(240), default="")


class RoleRecord(Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(240), default="")
    permissions: Mapped[list[PermissionRecord]] = relationship(
        secondary=role_permissions, lazy="selectin"
    )


class WorkItemRecord(Base):
    __tablename__ = "work_items"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    human_readable_id: Mapped[str] = mapped_column(String(30), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    type_code: Mapped[str] = mapped_column(String(80))
    type_id: Mapped[UUID | None] = mapped_column(ForeignKey("work_item_types.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    priority: Mapped[str] = mapped_column(String(20), index=True)
    impact: Mapped[str] = mapped_column(String(30), default="INDIVIDUAL")
    urgency: Mapped[str] = mapped_column(String(20), default="NORMAL")
    category: Mapped[str] = mapped_column(String(120), default="")
    source_department_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    destination_department_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    branch: Mapped[str] = mapped_column(String(160), default="")
    expected_deliverable: Mapped[str] = mapped_column(String(500), default="")
    custom_data: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_by: Mapped[UUID] = mapped_column(Uuid)
    assigned_to: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    workflow_id: Mapped[UUID | None] = mapped_column(ForeignKey("workflows.id"), nullable=True)
    workflow_state_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workflow_states.id"), nullable=True
    )
    sla_id: Mapped[UUID | None] = mapped_column(ForeignKey("slas.id"), nullable=True)
    response_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_escalated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    tags: Mapped[list["TagRecord"]] = relationship(secondary=work_item_tags, lazy="selectin")


class WorkItemTypeRecord(Base):
    __tablename__ = "work_item_types"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500), default="")
    active: Mapped[bool] = mapped_column(default=True)
    form_schema: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class TagRecord(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    name: Mapped[str] = mapped_column(String(80))
    color: Mapped[str] = mapped_column(String(20), default="#65736c")


class CustomFieldDefinitionRecord(Base):
    __tablename__ = "custom_field_definitions"
    __table_args__ = (UniqueConstraint("organization_id", "key"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    key: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(120))
    field_type: Mapped[str] = mapped_column(String(30))
    required: Mapped[bool] = mapped_column(default=False)
    options: Mapped[list[object]] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(default=True)


class CustomFieldValueRecord(Base):
    __tablename__ = "custom_field_values"
    __table_args__ = (UniqueConstraint("work_item_id", "definition_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    work_item_id: Mapped[UUID] = mapped_column(ForeignKey("work_items.id"), index=True)
    definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("custom_field_definitions.id"), index=True
    )
    value: Mapped[object] = mapped_column(JSON)


class ProjectRecord(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), index=True)
    owner_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AssignmentRecord(Base):
    __tablename__ = "assignments"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    work_item_id: Mapped[UUID] = mapped_column(ForeignKey("work_items.id"), index=True)
    assignee_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    assigned_by: Mapped[UUID] = mapped_column(Uuid)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CommentRecord(Base):
    __tablename__ = "comments"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    work_item_id: Mapped[UUID] = mapped_column(ForeignKey("work_items.id"), index=True)
    author_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    body: Mapped[str] = mapped_column(Text)
    internal: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ChecklistRecord(Base):
    __tablename__ = "checklists"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    work_item_id: Mapped[UUID] = mapped_column(ForeignKey("work_items.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ChecklistItemRecord(Base):
    __tablename__ = "checklist_items"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    checklist_id: Mapped[UUID] = mapped_column(ForeignKey("checklists.id"), index=True)
    text: Mapped[str] = mapped_column(String(500))
    completed: Mapped[bool] = mapped_column(default=False)
    position: Mapped[int] = mapped_column(default=0)
    completed_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ActivityEventRecord(Base):
    __tablename__ = "activity_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    work_item_id: Mapped[UUID] = mapped_column(ForeignKey("work_items.id"), index=True)
    actor_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    message: Mapped[str] = mapped_column(String(500))
    data: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class NotificationRecord(Base):
    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    recipient_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    kind: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(500))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[UUID] = mapped_column(Uuid)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AttachmentRecord(Base):
    __tablename__ = "attachments"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    work_item_id: Mapped[UUID] = mapped_column(ForeignKey("work_items.id"), index=True)
    uploaded_by: Mapped[UUID] = mapped_column(Uuid)
    original_name: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(120))
    size: Mapped[int] = mapped_column()
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkItemRelationRecord(Base):
    __tablename__ = "work_item_relations"
    __table_args__ = (
        UniqueConstraint("organization_id", "source_id", "target_id", "relation_type"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("work_items.id"), index=True)
    target_id: Mapped[UUID] = mapped_column(ForeignKey("work_items.id"), index=True)
    relation_type: Mapped[str] = mapped_column(String(40))
    created_by: Mapped[UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkflowRecord(Base):
    __tablename__ = "workflows"
    __table_args__ = (UniqueConstraint("organization_id", "name", "version"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(default=1)
    active: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkflowStateRecord(Base):
    __tablename__ = "workflow_states"
    __table_args__ = (UniqueConstraint("workflow_id", "code"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflows.id"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(120))
    initial: Mapped[bool] = mapped_column(default=False)
    terminal: Mapped[bool] = mapped_column(default=False)
    position: Mapped[int] = mapped_column(default=0)


class WorkflowTransitionRecord(Base):
    __tablename__ = "workflow_transitions"
    __table_args__ = (UniqueConstraint("workflow_id", "from_state_id", "to_state_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflows.id"), index=True)
    from_state_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_states.id"))
    to_state_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_states.id"))
    required_permission: Mapped[str] = mapped_column(String(100), default="workitem.update")
    requires_approval: Mapped[bool] = mapped_column(default=False)


class ApprovalRequestRecord(Base):
    __tablename__ = "approval_requests"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    work_item_id: Mapped[UUID] = mapped_column(ForeignKey("work_items.id"), index=True)
    requested_by: Mapped[UUID] = mapped_column(Uuid)
    requested_from: Mapped[UUID] = mapped_column(Uuid, index=True)
    reason: Mapped[str] = mapped_column(Text)
    amount: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    decision_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    decision_comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DeliverableRecord(Base):
    __tablename__ = "deliverables"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    work_item_id: Mapped[UUID] = mapped_column(ForeignKey("work_items.id"), index=True)
    submitted_by: Mapped[UUID] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String(40))
    content: Mapped[str] = mapped_column(Text)
    attachment_id: Mapped[UUID | None] = mapped_column(ForeignKey("attachments.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    review_comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SLARecord(Base):
    __tablename__ = "slas"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    name: Mapped[str] = mapped_column(String(120))
    response_minutes: Mapped[int] = mapped_column()
    resolution_minutes: Mapped[int] = mapped_column()
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    active: Mapped[bool] = mapped_column(default=True)


class AutomationRecord(Base):
    __tablename__ = "automations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    name: Mapped[str] = mapped_column(String(120))
    trigger_event: Mapped[str] = mapped_column(String(100), index=True)
    conditions: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    actions: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(default=True)
    created_by: Mapped[UUID] = mapped_column(Uuid)


class AutomationRunRecord(Base):
    __tablename__ = "automation_runs"
    __table_args__ = (UniqueConstraint("automation_id", "event_key"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    automation_id: Mapped[UUID] = mapped_column(ForeignKey("automations.id"), index=True)
    entity_id: Mapped[UUID] = mapped_column(Uuid)
    event_key: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(30))
    result: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IntegrationRecord(Base):
    __tablename__ = "integrations"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    name: Mapped[str] = mapped_column(String(120))
    provider: Mapped[str] = mapped_column(String(40), index=True)
    direction: Mapped[str] = mapped_column(String(20))
    config: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    secret_ref: Mapped[str] = mapped_column(String(160))
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IdentityLinkRecord(Base):
    __tablename__ = "identity_links"
    __table_args__ = (UniqueConstraint("integration_id", "external_user_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    integration_id: Mapped[UUID] = mapped_column(ForeignKey("integrations.id"), index=True)
    external_user_id: Mapped[str] = mapped_column(String(200))
    user_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WebhookReceiptRecord(Base):
    __tablename__ = "webhook_receipts"
    __table_args__ = (UniqueConstraint("integration_id", "external_event_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    integration_id: Mapped[UUID] = mapped_column(ForeignKey("integrations.id"), index=True)
    external_event_id: Mapped[str] = mapped_column(String(200))
    payload_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InboundMessageRecord(Base):
    __tablename__ = "inbound_messages"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    integration_id: Mapped[UUID] = mapped_column(ForeignKey("integrations.id"), index=True)
    channel: Mapped[str] = mapped_column(String(30), index=True)
    external_event_id: Mapped[str] = mapped_column(String(200))
    external_user_id: Mapped[str] = mapped_column(String(200), index=True)
    text: Mapped[str] = mapped_column(Text)
    normalized: Mapped[dict[str, object]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), index=True)
    work_item_id: Mapped[UUID | None] = mapped_column(ForeignKey("work_items.id"), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OutboundMessageRecord(Base):
    __tablename__ = "outbound_messages"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    integration_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("integrations.id"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(30), index=True)
    recipient: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ExternalEntityReferenceRecord(Base):
    __tablename__ = "external_entity_references"
    __table_args__ = (UniqueConstraint("integration_id", "entity_type", "external_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    integration_id: Mapped[UUID] = mapped_column(ForeignKey("integrations.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    external_id: Mapped[str] = mapped_column(String(200))
    external_url: Mapped[str] = mapped_column(String(1000), default="")
    snapshot: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class NotificationPreferenceRecord(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", "channel"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    channel: Mapped[str] = mapped_column(String(30))
    enabled: Mapped[bool] = mapped_column(default=True)
    quiet_hours: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class AgentRecord(Base):
    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500), default="")
    active: Mapped[bool] = mapped_column(default=True)
    risk_level: Mapped[str] = mapped_column(String(20), default="LOW")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AgentCapabilityRecord(Base):
    __tablename__ = "agent_capabilities"
    __table_args__ = (UniqueConstraint("agent_id", "code"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), index=True)
    code: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str] = mapped_column(String(300), default="")


class AgentPermissionRecord(Base):
    __tablename__ = "agent_permissions"
    __table_args__ = (UniqueConstraint("agent_id", "permission_code"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), index=True)
    permission_code: Mapped[str] = mapped_column(String(100))


class AgentRunRecord(Base):
    __tablename__ = "agent_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), index=True)
    requested_by: Mapped[UUID] = mapped_column(Uuid, index=True)
    capability: Mapped[str] = mapped_column(String(100))
    input_summary: Mapped[str] = mapped_column(String(500))
    output: Mapped[dict[str, object]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentActionProposalRecord(Base):
    __tablename__ = "agent_action_proposals"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    agent_run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    proposed_by: Mapped[UUID] = mapped_column(Uuid)
    action_type: Mapped[str] = mapped_column(String(80))
    target_type: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    arguments: Mapped[dict[str, object]] = mapped_column(JSON)
    risk_level: Mapped[str] = mapped_column(String(20))
    rationale: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(30), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentApprovalRecord(Base):
    __tablename__ = "agent_approvals"
    __table_args__ = (UniqueConstraint("proposal_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    proposal_id: Mapped[UUID] = mapped_column(ForeignKey("agent_action_proposals.id"), index=True)
    decided_by: Mapped[UUID] = mapped_column(Uuid)
    decision: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str] = mapped_column(String(1000), default="")
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProcessRecommendationRecord(Base):
    __tablename__ = "process_recommendations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    kind: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(200))
    evidence: Mapped[dict[str, object]] = mapped_column(JSON)
    recommendation: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(30), default="OPEN")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OutboxEventRecord(Base):
    __tablename__ = "outbox_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(80))
    aggregate_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ExpectedDeliverableRecord(Base):
    __tablename__ = "expected_deliverables"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    work_item_id: Mapped[UUID] = mapped_column(ForeignKey("work_items.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(String(1000))
    required: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    actor_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    new_state: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


settings = get_settings()
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def create_schema() -> None:
    Base.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
