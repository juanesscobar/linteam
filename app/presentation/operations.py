from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.application.auth import ActorContext
from app.domain.models import WorkItemStatus
from app.infrastructure.database import (
    ActivityEventRecord,
    AssignmentRecord,
    AttachmentRecord,
    ChecklistItemRecord,
    ChecklistRecord,
    CommentRecord,
    MembershipRecord,
    NotificationRecord,
    OutboxEventRecord,
    UserRecord,
    WorkflowRecord,
    WorkflowStateRecord,
    WorkflowTransitionRecord,
    WorkItemRecord,
    WorkItemRelationRecord,
    get_session,
)
from app.infrastructure.events import LoggingEventPublisher
from app.infrastructure.files import LocalFileStorage
from app.infrastructure.sql_repositories import record_audit, record_event
from app.presentation.auth import current_actor
from app.settings import Settings, get_settings

ALLOWED_TRANSITIONS: dict[WorkItemStatus, set[WorkItemStatus]] = {
    WorkItemStatus.NEW: {WorkItemStatus.ASSIGNED, WorkItemStatus.CANCELLED},
    WorkItemStatus.ASSIGNED: {WorkItemStatus.ACCEPTED, WorkItemStatus.CANCELLED},
    WorkItemStatus.ACCEPTED: {WorkItemStatus.IN_PROGRESS, WorkItemStatus.CANCELLED},
    WorkItemStatus.IN_PROGRESS: {
        WorkItemStatus.WAITING,
        WorkItemStatus.BLOCKED,
        WorkItemStatus.REVIEW,
        WorkItemStatus.COMPLETED,
    },
    WorkItemStatus.WAITING: {WorkItemStatus.IN_PROGRESS, WorkItemStatus.CANCELLED},
    WorkItemStatus.BLOCKED: {WorkItemStatus.IN_PROGRESS, WorkItemStatus.CANCELLED},
    WorkItemStatus.REVIEW: {
        WorkItemStatus.IN_PROGRESS,
        WorkItemStatus.APPROVAL_REQUIRED,
        WorkItemStatus.COMPLETED,
    },
    WorkItemStatus.APPROVAL_REQUIRED: {WorkItemStatus.COMPLETED, WorkItemStatus.REJECTED},
    WorkItemStatus.REJECTED: {WorkItemStatus.IN_PROGRESS, WorkItemStatus.CANCELLED},
    WorkItemStatus.COMPLETED: {WorkItemStatus.ARCHIVED},
    WorkItemStatus.CANCELLED: {WorkItemStatus.ARCHIVED},
    WorkItemStatus.ARCHIVED: set(),
}

STATE_LABELS = {
    "NEW": "Nuevo",
    "ASSIGNED": "Asignado",
    "ACCEPTED": "Aceptado",
    "IN_PROGRESS": "En progreso",
    "WAITING": "En espera",
    "BLOCKED": "Bloqueado",
    "REVIEW": "En revisión",
    "APPROVAL_REQUIRED": "Requiere aprobación",
    "COMPLETED": "Completado",
    "CANCELLED": "Cancelado",
    "ARCHIVED": "Archivado",
}


class AssignmentInput(BaseModel):
    assignee_id: UUID


class StatusInput(BaseModel):
    status: WorkItemStatus


class CommentInput(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)
    internal: bool = False
    mention_user_ids: list[UUID] = Field(default_factory=list)


class CommentView(CommentInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    author_id: UUID
    created_at: datetime


class ChecklistInput(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    items: list[str] = Field(min_length=1, max_length=100)


class ChecklistItemView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    text: str
    completed: bool
    position: int


class ActivityView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    actor_id: UUID | None
    event_type: str
    message: str
    data: dict[str, object]
    created_at: datetime


class NotificationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: str
    title: str
    body: str
    entity_type: str
    entity_id: UUID
    read_at: datetime | None
    created_at: datetime


class RelationInput(BaseModel):
    target_id: UUID
    relation_type: str = Field(pattern="^(SUBTASK|DEPENDS_ON|RELATED|DUPLICATES)$")


class AttachmentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    original_name: str
    content_type: str
    size: int
    checksum_sha256: str
    created_at: datetime


class ExecutiveSummary(BaseModel):
    total: int
    overdue: int
    unassigned: int
    completed: int
    by_status: dict[str, int]


router = APIRouter(prefix="/api/v1")


def get_work_item(session: Session, actor: ActorContext, work_item_id: UUID) -> WorkItemRecord:
    item = session.scalar(
        select(WorkItemRecord).where(
            WorkItemRecord.id == work_item_id,
            WorkItemRecord.organization_id == actor.organization_id,
        )
    )
    if item is None:
        raise HTTPException(404, "Work item not found")
    return item


def add_activity(
    session: Session,
    actor: ActorContext,
    item: WorkItemRecord,
    event_type: str,
    message: str,
    data: dict[str, object] | None = None,
) -> None:
    session.add(
        ActivityEventRecord(
            id=uuid4(),
            organization_id=actor.organization_id,
            work_item_id=item.id,
            actor_id=actor.user_id,
            event_type=event_type,
            message=message,
            data=data or {},
            created_at=datetime.now(UTC),
        )
    )


@router.post("/work-items/{work_item_id}/assign", status_code=204)
def assign(
    work_item_id: UUID,
    payload: AssignmentInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    actor.require("workitem.assign")
    item = get_work_item(session, actor, work_item_id)
    membership = session.scalar(
        select(MembershipRecord).where(
            MembershipRecord.user_id == payload.assignee_id,
            MembershipRecord.organization_id == actor.organization_id,
        )
    )
    if membership is None:
        raise HTTPException(404, "Assignee not found")
    now = datetime.now(UTC)
    item.assigned_to = payload.assignee_id
    item.status = WorkItemStatus.ASSIGNED.value
    item.updated_at = now
    session.add(
        AssignmentRecord(
            id=uuid4(),
            organization_id=actor.organization_id,
            work_item_id=item.id,
            assignee_id=payload.assignee_id,
            assigned_by=actor.user_id,
            accepted_at=None,
            created_at=now,
        )
    )
    session.add(
        NotificationRecord(
            id=uuid4(),
            organization_id=actor.organization_id,
            recipient_id=payload.assignee_id,
            kind="ASSIGNMENT",
            title=f"Asignación {item.human_readable_id}",
            body=item.title,
            entity_type="work_item",
            entity_id=item.id,
            read_at=None,
            created_at=now,
        )
    )
    add_activity(
        session,
        actor,
        item,
        "WorkItemAssigned",
        "Trabajo asignado",
        {"assignee_id": str(payload.assignee_id)},
    )
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="workitem.assign",
        entity_type="work_item",
        entity_id=item.id,
        new_state={"assigned_to": str(payload.assignee_id)},
    )
    record_event(
        session,
        organization_id=actor.organization_id,
        aggregate_type="work_item",
        aggregate_id=item.id,
        event_type="WorkItemAssigned",
        payload={"assignee_id": str(payload.assignee_id)},
    )
    session.commit()


@router.post("/work-items/{work_item_id}/status", status_code=204)
def change_status(
    work_item_id: UUID,
    payload: StatusInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    actor.require("workitem.update")
    item = get_work_item(session, actor, work_item_id)
    current = WorkItemStatus(item.status)
    can_manage_pipeline = "*" in actor.permissions or "workitem.assign" in actor.permissions
    if not can_manage_pipeline and payload.status not in ALLOWED_TRANSITIONS[current]:
        raise HTTPException(409, f"Transition {current} -> {payload.status} is not allowed")
    if (
        payload.status == WorkItemStatus.ACCEPTED
        and not can_manage_pipeline
        and item.assigned_to != actor.user_id
    ):
        raise HTTPException(403, "Only the assignee can accept this work")
    item.status = payload.status.value
    item.updated_at = datetime.now(UTC)
    if payload.status == WorkItemStatus.ACCEPTED:
        item.responded_at = item.updated_at
        assignment = session.scalar(
            select(AssignmentRecord)
            .where(
                AssignmentRecord.work_item_id == item.id,
                AssignmentRecord.assignee_id == actor.user_id,
            )
            .order_by(AssignmentRecord.created_at.desc())
        )
        if assignment:
            assignment.accepted_at = item.updated_at
    add_activity(
        session, actor, item, "WorkItemStatusChanged", f"Estado cambiado a {payload.status.value}"
    )
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="workitem.status",
        entity_type="work_item",
        entity_id=item.id,
        new_state={"status": payload.status.value},
    )
    record_event(
        session,
        organization_id=actor.organization_id,
        aggregate_type="work_item",
        aggregate_id=item.id,
        event_type="WorkItemStatusChanged",
        payload={"from": current.value, "to": payload.status.value},
    )
    session.commit()


@router.post("/work-items/{work_item_id}/comments", response_model=CommentView, status_code=201)
def comment(
    work_item_id: UUID,
    payload: CommentInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    actor.require("workitem.update")
    item = get_work_item(session, actor, work_item_id)
    if payload.mention_user_ids:
        valid_mentions = set(
            session.scalars(
                select(MembershipRecord.user_id).where(
                    MembershipRecord.organization_id == actor.organization_id,
                    MembershipRecord.user_id.in_(payload.mention_user_ids),
                )
            ).all()
        )
        if valid_mentions != set(payload.mention_user_ids):
            raise HTTPException(404, "Mentioned member not found")
    value = CommentRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        work_item_id=item.id,
        author_id=actor.user_id,
        body=payload.body.strip(),
        internal=payload.internal,
        created_at=datetime.now(UTC),
    )
    session.add(value)
    for recipient_id in set(payload.mention_user_ids) - {actor.user_id}:
        session.add(
            NotificationRecord(
                id=uuid4(),
                organization_id=actor.organization_id,
                recipient_id=recipient_id,
                kind="MENTION",
                title=f"Mención en {item.human_readable_id}",
                body=payload.body[:500],
                entity_type="work_item",
                entity_id=item.id,
                read_at=None,
                created_at=datetime.now(UTC),
            )
        )
    add_activity(session, actor, item, "CommentCreated", "Comentario agregado")
    session.commit()
    return value


@router.get("/work-items/{work_item_id}/timeline", response_model=list[ActivityView])
def timeline(
    work_item_id: UUID,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    actor.require("workitem.view")
    get_work_item(session, actor, work_item_id)
    return session.scalars(
        select(ActivityEventRecord)
        .where(
            ActivityEventRecord.organization_id == actor.organization_id,
            ActivityEventRecord.work_item_id == work_item_id,
        )
        .order_by(ActivityEventRecord.created_at)
    ).all()


@router.post(
    "/work-items/{work_item_id}/checklists", response_model=list[ChecklistItemView], status_code=201
)
def checklist(
    work_item_id: UUID,
    payload: ChecklistInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    actor.require("workitem.update")
    item = get_work_item(session, actor, work_item_id)
    checklist_id = uuid4()
    session.add(
        ChecklistRecord(
            id=checklist_id,
            organization_id=actor.organization_id,
            work_item_id=item.id,
            title=payload.title.strip(),
            created_at=datetime.now(UTC),
        )
    )
    values = [
        ChecklistItemRecord(
            id=uuid4(),
            checklist_id=checklist_id,
            text=text.strip(),
            completed=False,
            position=position,
            completed_by=None,
            completed_at=None,
        )
        for position, text in enumerate(payload.items)
        if text.strip()
    ]
    if not values:
        raise HTTPException(422, "Checklist requires a non-empty item")
    session.add_all(values)
    add_activity(session, actor, item, "ChecklistCreated", f"Checklist creado: {payload.title}")
    session.commit()
    return values


@router.post("/checklist-items/{checklist_item_id}/toggle", response_model=ChecklistItemView)
def toggle_checklist_item(
    checklist_item_id: UUID,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    actor.require("workitem.update")
    value = session.scalar(
        select(ChecklistItemRecord)
        .join(ChecklistRecord, ChecklistRecord.id == ChecklistItemRecord.checklist_id)
        .where(
            ChecklistItemRecord.id == checklist_item_id,
            ChecklistRecord.organization_id == actor.organization_id,
        )
    )
    if value is None:
        raise HTTPException(404, "Checklist item not found")
    value.completed = not value.completed
    value.completed_by = actor.user_id if value.completed else None
    value.completed_at = datetime.now(UTC) if value.completed else None
    session.commit()
    return value


@router.post("/work-items/{work_item_id}/relations", status_code=201)
def relate_work_item(
    work_item_id: UUID,
    payload: RelationInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, UUID | str]:
    actor.require("workitem.update")
    source = get_work_item(session, actor, work_item_id)
    target = get_work_item(session, actor, payload.target_id)
    if source.id == target.id:
        raise HTTPException(422, "A work item cannot relate to itself")
    relation = WorkItemRelationRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        source_id=source.id,
        target_id=target.id,
        relation_type=payload.relation_type,
        created_by=actor.user_id,
        created_at=datetime.now(UTC),
    )
    session.add(relation)
    add_activity(
        session,
        actor,
        source,
        "WorkItemRelated",
        f"Relación creada: {payload.relation_type}",
        {"target_id": str(target.id)},
    )
    session.commit()
    return {"id": relation.id, "relation_type": relation.relation_type}


@router.post(
    "/work-items/{work_item_id}/attachments", response_model=AttachmentView, status_code=201
)
async def upload_attachment(
    work_item_id: UUID,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File()],
) -> object:
    actor.require("workitem.update")
    item = get_work_item(session, actor, work_item_id)
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(413, "File is too large")
    if not content:
        raise HTTPException(422, "File is empty")
    attachment_id = uuid4()
    stored = LocalFileStorage(settings.file_storage_path).save(
        actor.organization_id, attachment_id, content
    )
    attachment = AttachmentRecord(
        id=attachment_id,
        organization_id=actor.organization_id,
        work_item_id=item.id,
        uploaded_by=actor.user_id,
        original_name=(file.filename or "file")[:255],
        storage_key=stored.storage_key,
        content_type=(file.content_type or "application/octet-stream")[:120],
        size=stored.size,
        checksum_sha256=stored.checksum_sha256,
        created_at=datetime.now(UTC),
    )
    session.add(attachment)
    add_activity(
        session, actor, item, "AttachmentUploaded", f"Archivo adjuntado: {attachment.original_name}"
    )
    session.commit()
    return attachment


@router.get("/attachments/{attachment_id}/content")
def download_attachment(
    attachment_id: UUID,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    actor.require("workitem.view")
    attachment = session.scalar(
        select(AttachmentRecord).where(
            AttachmentRecord.id == attachment_id,
            AttachmentRecord.organization_id == actor.organization_id,
        )
    )
    if attachment is None:
        raise HTTPException(404, "Attachment not found")
    try:
        path = LocalFileStorage(settings.file_storage_path).path(attachment.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Attachment content not found") from exc
    return FileResponse(path, media_type=attachment.content_type, filename=attachment.original_name)


@router.get("/my-work")
def my_work(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> list[dict[str, object]]:
    actor.require("workitem.view")
    items = session.scalars(
        select(WorkItemRecord)
        .where(
            WorkItemRecord.organization_id == actor.organization_id,
            or_(
                WorkItemRecord.assigned_to == actor.user_id,
                WorkItemRecord.id.in_(
                    select(AssignmentRecord.work_item_id).where(
                        AssignmentRecord.organization_id == actor.organization_id,
                        AssignmentRecord.assignee_id == actor.user_id,
                    )
                ),
                WorkItemRecord.created_by == actor.user_id,
            ),
            WorkItemRecord.status.notin_(
                [WorkItemStatus.ARCHIVED.value, WorkItemStatus.CANCELLED.value]
            ),
        )
        .order_by(WorkItemRecord.due_at.asc().nullslast(), WorkItemRecord.created_at.desc())
    ).all()
    return [
        {
            "id": item.id,
            "reference": item.human_readable_id,
            "title": item.title,
            "status": item.status,
            "priority": item.priority,
            "due_at": item.due_at,
        }
        for item in items
    ]


@router.get("/analytics/executive", response_model=ExecutiveSummary)
def executive_summary(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> ExecutiveSummary:
    actor.require("executive.view")
    base = WorkItemRecord.organization_id == actor.organization_id
    rows = session.execute(
        select(WorkItemRecord.status, func.count()).where(base).group_by(WorkItemRecord.status)
    ).all()
    by_status = {status: count for status, count in rows}
    now = datetime.now(UTC)
    overdue = (
        session.scalar(
            select(func.count())
            .select_from(WorkItemRecord)
            .where(
                base,
                WorkItemRecord.due_at < now,
                WorkItemRecord.status.notin_(
                    [WorkItemStatus.COMPLETED.value, WorkItemStatus.ARCHIVED.value]
                ),
            )
        )
        or 0
    )
    unassigned = (
        session.scalar(
            select(func.count())
            .select_from(WorkItemRecord)
            .where(base, WorkItemRecord.assigned_to.is_(None))
        )
        or 0
    )
    return ExecutiveSummary(
        total=sum(by_status.values()),
        overdue=overdue,
        unassigned=unassigned,
        completed=by_status.get(WorkItemStatus.COMPLETED.value, 0),
        by_status=by_status,
    )


@router.get("/notifications", response_model=list[NotificationView])
def notifications(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    return session.scalars(
        select(NotificationRecord)
        .where(
            NotificationRecord.organization_id == actor.organization_id,
            NotificationRecord.recipient_id == actor.user_id,
        )
        .order_by(NotificationRecord.created_at.desc())
    ).all()


@router.post("/notifications/{notification_id}/read", status_code=204)
def read_notification(
    notification_id: UUID,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    notification = session.scalar(
        select(NotificationRecord).where(
            NotificationRecord.id == notification_id,
            NotificationRecord.organization_id == actor.organization_id,
            NotificationRecord.recipient_id == actor.user_id,
        )
    )
    if notification is None:
        raise HTTPException(404, "Notification not found")
    notification.read_at = datetime.now(UTC)
    session.commit()


@router.post("/jobs/outbox-publish")
def publish_outbox(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
    limit: int = 100,
) -> dict[str, int]:
    actor.require("system.jobs")
    now = datetime.now(UTC)
    events = session.scalars(
        select(OutboxEventRecord)
        .where(
            OutboxEventRecord.organization_id == actor.organization_id,
            OutboxEventRecord.status.in_(["PENDING", "RETRY"]),
            OutboxEventRecord.next_attempt_at <= now,
        )
        .order_by(OutboxEventRecord.occurred_at)
        .limit(min(max(limit, 1), 500))
    ).all()
    publisher = LoggingEventPublisher()
    published = retried = 0
    for event in events:
        try:
            publisher.publish(event.id, event.event_type, event.payload)
            event.status, event.published_at = "PUBLISHED", now
            event.attempts += 1
            published += 1
        except RuntimeError:
            event.attempts += 1
            event.status = "DEAD_LETTER" if event.attempts >= 5 else "RETRY"
            event.next_attempt_at = now + timedelta(minutes=2**event.attempts)
            retried += 1
    session.commit()
    return {"published": published, "retried": retried}


class PipelineStateView(BaseModel):
    code: str
    name: str
    position: int
    initial: bool
    terminal: bool
    count: int = 0


class PipelineCardView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    human_readable_id: str
    title: str
    type_code: str
    priority: str
    status: str
    assigned_to: UUID | None
    assignee_name: str | None = None
    source_department_id: UUID | None = None
    branch: str = ""
    due_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    is_overdue: bool = False
    is_blocked: bool = False


class PipelineBoardView(BaseModel):
    workflow_id: UUID | None = None
    workflow_name: str | None = None
    states: list[PipelineStateView]
    cards: list[PipelineCardView]
    members: list[dict[str, object]]


@router.get("/pipeline/board", response_model=PipelineBoardView)
def pipeline_board(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
    status_filter: str | None = None,
    priority_filter: str | None = None,
    assignee_filter: UUID | None = None,
    department_filter: UUID | None = None,
    branch_filter: str | None = None,
    overdue_only: bool = False,
    tag_filter: str | None = None,
) -> PipelineBoardView:
    actor.require("workitem.view")
    workflow = session.scalar(
        select(WorkflowRecord).where(
            WorkflowRecord.organization_id == actor.organization_id,
            WorkflowRecord.active.is_(True),
        )
    )
    states: list[PipelineStateView] = []
    if workflow is not None:
        state_records = session.scalars(
            select(WorkflowStateRecord)
            .where(WorkflowStateRecord.workflow_id == workflow.id)
            .order_by(WorkflowStateRecord.position)
        ).all()
        states = [
            PipelineStateView(
                code=s.code,
                name=STATE_LABELS.get(s.code, s.name),
                position=s.position,
                initial=s.initial,
                terminal=s.terminal,
            )
            for s in state_records
        ]
    else:
        for position, code in enumerate(
            [
                WorkItemStatus.NEW,
                WorkItemStatus.ASSIGNED,
                WorkItemStatus.ACCEPTED,
                WorkItemStatus.IN_PROGRESS,
                WorkItemStatus.WAITING,
                WorkItemStatus.BLOCKED,
                WorkItemStatus.REVIEW,
                WorkItemStatus.APPROVAL_REQUIRED,
                WorkItemStatus.COMPLETED,
            ]
        ):
            states.append(
                PipelineStateView(
                    code=code.value,
                    name=STATE_LABELS[code.value],
                    position=position,
                    initial=code == WorkItemStatus.NEW,
                    terminal=code in (WorkItemStatus.COMPLETED, WorkItemStatus.CANCELLED),
                )
            )
    base_filters = [
        WorkItemRecord.organization_id == actor.organization_id,
        WorkItemRecord.status.notin_(
            [WorkItemStatus.ARCHIVED.value, WorkItemStatus.CANCELLED.value]
        ),
    ]
    if status_filter:
        base_filters.append(WorkItemRecord.status == status_filter)
    if priority_filter:
        base_filters.append(WorkItemRecord.priority == priority_filter)
    if assignee_filter:
        base_filters.append(WorkItemRecord.assigned_to == assignee_filter)
    if department_filter:
        base_filters.append(
            or_(
                WorkItemRecord.source_department_id == department_filter,
                WorkItemRecord.destination_department_id == department_filter,
            )
        )
    if branch_filter:
        base_filters.append(WorkItemRecord.branch == branch_filter)
    now = datetime.now(UTC)
    if overdue_only:
        base_filters.append(WorkItemRecord.due_at < now)
        base_filters.append(
            WorkItemRecord.status.notin_(
                [WorkItemStatus.COMPLETED.value, WorkItemStatus.ARCHIVED.value]
            )
        )
    items = session.scalars(
        select(WorkItemRecord)
        .where(*base_filters)
        .order_by(
            WorkItemRecord.due_at.asc().nullslast(),
            WorkItemRecord.priority.desc(),
            WorkItemRecord.created_at.desc(),
        )
    ).all()
    if tag_filter:
        items = [item for item in items if any(t.name == tag_filter for t in item.tags)]
    state_code_set = {s.code for s in states}
    count_by_status: dict[str, int] = {}
    for item in items:
        count_by_status[item.status] = count_by_status.get(item.status, 0) + 1
    for s in states:
        s.count = count_by_status.get(s.code, 0)
    user_ids = {item.assigned_to for item in items if item.assigned_to}
    user_names: dict[UUID, str] = {}
    if user_ids:
        users = session.scalars(select(UserRecord).where(UserRecord.id.in_(user_ids))).all()
        user_names = {u.id: u.name for u in users}
    cards = []
    for item in items:
        if item.status not in state_code_set:
            continue
        is_overdue = (
            item.due_at is not None
            and item.due_at < now
            and item.status not in (WorkItemStatus.COMPLETED.value, WorkItemStatus.ARCHIVED.value)
        )
        cards.append(
            PipelineCardView(
                id=item.id,
                human_readable_id=item.human_readable_id,
                title=item.title,
                type_code=item.type_code,
                priority=item.priority,
                status=item.status,
                assigned_to=item.assigned_to,
                assignee_name=user_names.get(item.assigned_to) if item.assigned_to else None,
                source_department_id=item.source_department_id,
                branch=item.branch,
                due_at=item.due_at,
                created_at=item.created_at,
                updated_at=item.updated_at,
                is_overdue=is_overdue,
                is_blocked=item.status == WorkItemStatus.BLOCKED.value,
            )
        )
    members = session.scalars(
        select(MembershipRecord).where(
            MembershipRecord.organization_id == actor.organization_id,
        )
    ).all()
    member_list = []
    for m in members:
        user = session.get(UserRecord, m.user_id)
        if user:
            member_list.append({"id": str(m.user_id), "name": user.name})
    return PipelineBoardView(
        workflow_id=workflow.id if workflow else None,
        workflow_name=workflow.name if workflow else None,
        states=states,
        cards=cards,
        members=member_list,
    )


@router.get("/pipeline/transitions")
def pipeline_transitions(
    work_item_id: UUID,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> list[dict[str, str]]:
    actor.require("workitem.view")
    item = get_work_item(session, actor, work_item_id)
    if item.workflow_id and item.workflow_state_id:
        transitions = session.scalars(
            select(WorkflowTransitionRecord, WorkflowStateRecord)
            .join(
                WorkflowStateRecord,
                WorkflowTransitionRecord.to_state_id == WorkflowStateRecord.id,
            )
            .where(
                WorkflowTransitionRecord.workflow_id == item.workflow_id,
                WorkflowTransitionRecord.from_state_id == item.workflow_state_id,
            )
        ).all()
        return [{"code": t[1].code, "name": t[1].name} for t in transitions]
    current = WorkItemStatus(item.status)
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    return [{"code": s.value, "name": s.value.replace("_", " ").title()} for s in allowed]
