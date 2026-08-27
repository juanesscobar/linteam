from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.auth import ActorContext
from app.infrastructure.database import (
    ApprovalRequestRecord,
    AttachmentRecord,
    AutomationRecord,
    AutomationRunRecord,
    DeliverableRecord,
    ExpectedDeliverableRecord,
    MembershipRecord,
    NotificationRecord,
    SLARecord,
    WorkflowRecord,
    WorkflowStateRecord,
    WorkflowTransitionRecord,
    WorkItemRecord,
    get_session,
)
from app.infrastructure.sql_repositories import record_audit
from app.presentation.auth import current_actor
from app.presentation.operations import add_activity, get_work_item


class StateInput(BaseModel):
    code: str = Field(pattern="^[A-Z][A-Z0-9_]{1,79}$")
    name: str = Field(min_length=2, max_length=120)
    initial: bool = False
    terminal: bool = False


class TransitionInput(BaseModel):
    from_code: str
    to_code: str
    required_permission: str = "workitem.update"
    requires_approval: bool = False


class WorkflowInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    states: list[StateInput] = Field(min_length=2, max_length=100)
    transitions: list[TransitionInput] = Field(min_length=1, max_length=300)
    activate: bool = False


class WorkflowView(BaseModel):
    id: UUID
    name: str
    version: int
    active: bool
    states: list[StateInput]
    transitions: list[TransitionInput]


class ApprovalInput(BaseModel):
    requested_from: UUID
    reason: str = Field(min_length=3, max_length=5000)
    amount: Decimal | None = Field(default=None, ge=0)


class DecisionInput(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    comment: str = Field(default="", max_length=5000)


class ApprovalView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    work_item_id: UUID
    requested_by: UUID
    requested_from: UUID
    reason: str
    amount: str | None
    status: str
    decision_comment: str
    created_at: datetime
    decided_at: datetime | None


class DeliverableInput(BaseModel):
    kind: Literal["TEXT", "LINK", "FILE", "CONFIRMATION"]
    content: str = Field(default="", max_length=20_000)
    attachment_id: UUID | None = None


class DeliverableReview(BaseModel):
    status: Literal["APPROVED", "REJECTED", "REVISION_REQUIRED"]
    comment: str = Field(default="", max_length=5000)


class DeliverableView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    work_item_id: UUID
    submitted_by: UUID
    kind: str
    content: str
    attachment_id: UUID | None
    status: str
    review_comment: str
    created_at: datetime
    reviewed_at: datetime | None


class SLAInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    response_minutes: int = Field(ge=1, le=525_600)
    resolution_minutes: int = Field(ge=1, le=5_256_000)
    priority: str | None = Field(default=None, pattern="^(LOW|NORMAL|HIGH|CRITICAL)$")


class AutomationInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    trigger_event: str = Field(min_length=3, max_length=100)
    conditions: dict[str, object] = Field(default_factory=dict)
    actions: list[dict[str, object]] = Field(min_length=1, max_length=20)


class WorkflowAttachInput(BaseModel):
    workflow_id: UUID


class WorkflowMoveInput(BaseModel):
    to_code: str = Field(pattern="^[A-Z][A-Z0-9_]{1,79}$")


class SLAAttachInput(BaseModel):
    sla_id: UUID


class AutomationExecuteInput(BaseModel):
    entity_id: UUID
    event_key: str = Field(min_length=8, max_length=160)


router = APIRouter(prefix="/api/v1")


@router.post("/workflows", response_model=WorkflowView, status_code=201)
def create_workflow(
    payload: WorkflowInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> WorkflowView:
    actor.require("workflow.manage")
    codes = [state.code for state in payload.states]
    if len(codes) != len(set(codes)) or sum(state.initial for state in payload.states) != 1:
        raise HTTPException(422, "States must be unique and have exactly one initial state")
    for transition in payload.transitions:
        if transition.from_code not in codes or transition.to_code not in codes:
            raise HTTPException(422, "Transition references an unknown state")
    existing = session.scalars(
        select(WorkflowRecord).where(
            WorkflowRecord.organization_id == actor.organization_id,
            WorkflowRecord.name == payload.name,
        )
    ).all()
    workflow = WorkflowRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        name=payload.name.strip(),
        version=max((item.version for item in existing), default=0) + 1,
        active=payload.activate,
        created_at=datetime.now(UTC),
    )
    if payload.activate:
        for item in existing:
            item.active = False
    session.add(workflow)
    session.flush()
    states = {
        value.code: WorkflowStateRecord(
            id=uuid4(),
            workflow_id=workflow.id,
            code=value.code,
            name=value.name,
            initial=value.initial,
            terminal=value.terminal,
            position=position,
        )
        for position, value in enumerate(payload.states)
    }
    session.add_all(states.values())
    session.flush()
    session.add_all(
        [
            WorkflowTransitionRecord(
                id=uuid4(),
                workflow_id=workflow.id,
                from_state_id=states[value.from_code].id,
                to_state_id=states[value.to_code].id,
                required_permission=value.required_permission,
                requires_approval=value.requires_approval,
            )
            for value in payload.transitions
        ]
    )
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="workflow.create",
        entity_type="workflow",
        entity_id=workflow.id,
        new_state={"name": workflow.name, "version": workflow.version},
    )
    session.commit()
    return WorkflowView(
        id=workflow.id,
        name=workflow.name,
        version=workflow.version,
        active=workflow.active,
        states=payload.states,
        transitions=payload.transitions,
    )


@router.post("/work-items/{work_item_id}/workflow", status_code=204)
def attach_workflow(
    work_item_id: UUID,
    payload: WorkflowAttachInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    actor.require("workflow.manage")
    item = get_work_item(session, actor, work_item_id)
    workflow = session.scalar(
        select(WorkflowRecord).where(
            WorkflowRecord.id == payload.workflow_id,
            WorkflowRecord.organization_id == actor.organization_id,
            WorkflowRecord.active.is_(True),
        )
    )
    if workflow is None:
        raise HTTPException(404, "Active workflow not found")
    initial = session.scalar(
        select(WorkflowStateRecord).where(
            WorkflowStateRecord.workflow_id == workflow.id,
            WorkflowStateRecord.initial.is_(True),
        )
    )
    if initial is None:
        raise HTTPException(409, "Workflow has no initial state")
    item.workflow_id, item.workflow_state_id, item.status = workflow.id, initial.id, initial.code
    item.updated_at = datetime.now(UTC)
    add_activity(session, actor, item, "WorkflowAttached", f"Workflow aplicado: {workflow.name}")
    session.commit()


@router.post("/work-items/{work_item_id}/workflow-transition", status_code=204)
def execute_workflow_transition(
    work_item_id: UUID,
    payload: WorkflowMoveInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    item = get_work_item(session, actor, work_item_id)
    if item.workflow_id is None or item.workflow_state_id is None:
        raise HTTPException(409, "Work item has no workflow")
    target = session.scalar(
        select(WorkflowStateRecord).where(
            WorkflowStateRecord.workflow_id == item.workflow_id,
            WorkflowStateRecord.code == payload.to_code,
        )
    )
    if target is None:
        raise HTTPException(404, "Workflow state not found")
    transition = session.scalar(
        select(WorkflowTransitionRecord).where(
            WorkflowTransitionRecord.workflow_id == item.workflow_id,
            WorkflowTransitionRecord.from_state_id == item.workflow_state_id,
            WorkflowTransitionRecord.to_state_id == target.id,
        )
    )
    if transition is None:
        raise HTTPException(409, "Workflow transition is not allowed")
    actor.require(transition.required_permission)
    if transition.requires_approval:
        approved = session.scalar(
            select(ApprovalRequestRecord.id).where(
                ApprovalRequestRecord.work_item_id == item.id,
                ApprovalRequestRecord.organization_id == actor.organization_id,
                ApprovalRequestRecord.status == "APPROVED",
            )
        )
        if approved is None:
            raise HTTPException(409, "An approved request is required for this transition")
    previous = item.status
    item.workflow_state_id, item.status, item.updated_at = target.id, target.code, datetime.now(UTC)
    add_activity(session, actor, item, "WorkflowTransitioned", f"Estado {previous} → {target.code}")
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="workflow.transition",
        entity_type="work_item",
        entity_id=item.id,
        new_state={"status": target.code},
    )
    session.commit()


@router.post("/work-items/{work_item_id}/approvals", response_model=ApprovalView, status_code=201)
def request_approval(
    work_item_id: UUID,
    payload: ApprovalInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    actor.require("workitem.approve")
    item = get_work_item(session, actor, work_item_id)
    approver = session.scalar(
        select(MembershipRecord).where(
            MembershipRecord.organization_id == actor.organization_id,
            MembershipRecord.user_id == payload.requested_from,
        )
    )
    if approver is None:
        raise HTTPException(404, "Approver not found")
    approval = ApprovalRequestRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        work_item_id=item.id,
        requested_by=actor.user_id,
        requested_from=payload.requested_from,
        reason=payload.reason.strip(),
        amount=str(payload.amount) if payload.amount is not None else None,
        status="PENDING",
        decision_by=None,
        decision_comment="",
        created_at=datetime.now(UTC),
        decided_at=None,
    )
    session.add(approval)
    session.add(
        NotificationRecord(
            id=uuid4(),
            organization_id=actor.organization_id,
            recipient_id=payload.requested_from,
            kind="APPROVAL",
            title=f"Aprobación {item.human_readable_id}",
            body=payload.reason[:500],
            entity_type="approval",
            entity_id=approval.id,
            read_at=None,
            created_at=datetime.now(UTC),
        )
    )
    add_activity(
        session,
        actor,
        item,
        "ApprovalRequested",
        "Aprobación solicitada",
        {"approval_id": str(approval.id)},
    )
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="approval.request",
        entity_type="approval",
        entity_id=approval.id,
        new_state={"status": "PENDING"},
    )
    session.commit()
    return approval


@router.post("/approvals/{approval_id}/decision", response_model=ApprovalView)
def decide_approval(
    approval_id: UUID,
    payload: DecisionInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    approval = session.scalar(
        select(ApprovalRequestRecord).where(
            ApprovalRequestRecord.id == approval_id,
            ApprovalRequestRecord.organization_id == actor.organization_id,
        )
    )
    if approval is None:
        raise HTTPException(404, "Approval not found")
    if (
        approval.requested_from != actor.user_id
        and "workitem.approve.any" not in actor.permissions
        and "*" not in actor.permissions
    ):
        raise HTTPException(403, "Only the requested approver can decide")
    if approval.status != "PENDING":
        raise HTTPException(409, "Approval is already decided")
    approval.status, approval.decision_by = payload.decision, actor.user_id
    approval.decision_comment, approval.decided_at = payload.comment.strip(), datetime.now(UTC)
    item = get_work_item(session, actor, approval.work_item_id)
    add_activity(
        session,
        actor,
        item,
        f"Approval{payload.decision.title()}",
        f"Aprobación {payload.decision.lower()}",
    )
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="approval.decide",
        entity_type="approval",
        entity_id=approval.id,
        new_state={"status": approval.status, "comment": approval.decision_comment},
    )
    session.commit()
    return approval


@router.post(
    "/work-items/{work_item_id}/deliverables", response_model=DeliverableView, status_code=201
)
def submit_deliverable(
    work_item_id: UUID,
    payload: DeliverableInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    actor.require("workitem.update")
    item = get_work_item(session, actor, work_item_id)
    if payload.kind == "FILE":
        attachment = session.scalar(
            select(AttachmentRecord).where(
                AttachmentRecord.id == payload.attachment_id,
                AttachmentRecord.organization_id == actor.organization_id,
                AttachmentRecord.work_item_id == item.id,
            )
        )
        if attachment is None:
            raise HTTPException(404, "Attachment not found")
    elif not payload.content.strip():
        raise HTTPException(422, "Content is required for this deliverable type")
    value = DeliverableRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        work_item_id=item.id,
        submitted_by=actor.user_id,
        kind=payload.kind,
        content=payload.content.strip(),
        attachment_id=payload.attachment_id,
        status="SUBMITTED",
        review_comment="",
        created_at=datetime.now(UTC),
        reviewed_at=None,
    )
    session.add(value)
    expected = session.scalar(
        select(ExpectedDeliverableRecord)
        .where(
            ExpectedDeliverableRecord.organization_id == actor.organization_id,
            ExpectedDeliverableRecord.work_item_id == item.id,
            ExpectedDeliverableRecord.status == "PENDING",
        )
        .order_by(ExpectedDeliverableRecord.created_at)
    )
    if expected is not None:
        expected.status = "SUBMITTED"
    add_activity(
        session,
        actor,
        item,
        "DeliverableSubmitted",
        "Entregable enviado",
        {"deliverable_id": str(value.id)},
    )
    session.commit()
    return value


@router.post("/deliverables/{deliverable_id}/review", response_model=DeliverableView)
def review_deliverable(
    deliverable_id: UUID,
    payload: DeliverableReview,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    actor.require("workitem.approve")
    value = session.scalar(
        select(DeliverableRecord).where(
            DeliverableRecord.id == deliverable_id,
            DeliverableRecord.organization_id == actor.organization_id,
        )
    )
    if value is None:
        raise HTTPException(404, "Deliverable not found")
    value.status, value.review_comment, value.reviewed_at = (
        payload.status,
        payload.comment.strip(),
        datetime.now(UTC),
    )
    expected = session.scalar(
        select(ExpectedDeliverableRecord)
        .where(
            ExpectedDeliverableRecord.organization_id == actor.organization_id,
            ExpectedDeliverableRecord.work_item_id == value.work_item_id,
            ExpectedDeliverableRecord.status == "SUBMITTED",
        )
        .order_by(ExpectedDeliverableRecord.created_at)
    )
    if expected is not None:
        expected.status = payload.status
    item = get_work_item(session, actor, value.work_item_id)
    add_activity(session, actor, item, "DeliverableReviewed", f"Entregable: {payload.status}")
    session.commit()
    return value


@router.post("/slas", status_code=201)
def create_sla(
    payload: SLAInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("workflow.manage")
    if payload.resolution_minutes < payload.response_minutes:
        raise HTTPException(422, "Resolution target must be greater than response target")
    value = SLARecord(
        id=uuid4(), organization_id=actor.organization_id, active=True, **payload.model_dump()
    )
    session.add(value)
    session.commit()
    return {"id": value.id, **payload.model_dump(), "active": True}


@router.post("/automations", status_code=201)
def create_automation(
    payload: AutomationInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("automation.manage")
    allowed_actions = {"notify", "set_priority", "assign"}
    if any(action.get("type") not in allowed_actions for action in payload.actions):
        raise HTTPException(422, "Automation contains an unsupported action")
    value = AutomationRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        created_by=actor.user_id,
        active=True,
        **payload.model_dump(),
    )
    session.add(value)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="automation.create",
        entity_type="automation",
        entity_id=value.id,
        new_state={"name": value.name, "active": True},
    )
    session.commit()
    return {"id": value.id, "name": value.name, "active": value.active}


@router.post("/automations/{automation_id}/dry-run", status_code=201)
def dry_run_automation(
    automation_id: UUID,
    entity_id: UUID,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("automation.manage")
    automation = session.scalar(
        select(AutomationRecord).where(
            AutomationRecord.id == automation_id,
            AutomationRecord.organization_id == actor.organization_id,
        )
    )
    if automation is None:
        raise HTTPException(404, "Automation not found")
    run = AutomationRunRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        automation_id=automation.id,
        entity_id=entity_id,
        event_key=f"dry-run:{uuid4()}",
        status="DRY_RUN",
        result={"would_execute": automation.actions},
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    session.add(run)
    session.commit()
    return {"id": run.id, "status": run.status, "result": run.result}


@router.post("/work-items/{work_item_id}/sla", status_code=204)
def attach_sla(
    work_item_id: UUID,
    payload: SLAAttachInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    actor.require("workflow.manage")
    item = get_work_item(session, actor, work_item_id)
    sla = session.scalar(
        select(SLARecord).where(
            SLARecord.id == payload.sla_id,
            SLARecord.organization_id == actor.organization_id,
            SLARecord.active.is_(True),
        )
    )
    if sla is None:
        raise HTTPException(404, "SLA not found")
    now = datetime.now(UTC)
    item.sla_id = sla.id
    item.response_due_at = now + timedelta(minutes=sla.response_minutes)
    item.resolution_due_at = now + timedelta(minutes=sla.resolution_minutes)
    item.sla_escalated_at = None
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="sla.attach",
        entity_type="work_item",
        entity_id=item.id,
        new_state={
            "sla_id": str(sla.id),
            "response_due_at": item.response_due_at.isoformat(),
            "resolution_due_at": item.resolution_due_at.isoformat(),
        },
    )
    session.commit()


@router.post("/jobs/sla-monitor")
def monitor_slas(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, int]:
    actor.require("system.jobs")
    now = datetime.now(UTC)
    candidates = session.scalars(
        select(WorkItemRecord).where(
            WorkItemRecord.organization_id == actor.organization_id,
            WorkItemRecord.sla_id.is_not(None),
            WorkItemRecord.sla_escalated_at.is_(None),
            WorkItemRecord.resolution_due_at < now,
            WorkItemRecord.status.notin_(["COMPLETED", "ARCHIVED", "CANCELLED"]),
        )
    ).all()
    for item in candidates:
        recipient = item.assigned_to or item.created_by
        session.add(
            NotificationRecord(
                id=uuid4(),
                organization_id=actor.organization_id,
                recipient_id=recipient,
                kind="SLA_BREACH",
                title=f"SLA vencido: {item.human_readable_id}",
                body=item.title,
                entity_type="work_item",
                entity_id=item.id,
                read_at=None,
                created_at=now,
            )
        )
        item.sla_escalated_at = now
        add_activity(session, actor, item, "SLABreached", "SLA de resolución vencido")
    session.commit()
    return {"escalated": len(candidates)}


@router.post("/automations/{automation_id}/execute")
def execute_automation(
    automation_id: UUID,
    payload: AutomationExecuteInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("automation.execute")
    automation = session.scalar(
        select(AutomationRecord).where(
            AutomationRecord.id == automation_id,
            AutomationRecord.organization_id == actor.organization_id,
            AutomationRecord.active.is_(True),
        )
    )
    if automation is None:
        raise HTTPException(404, "Automation not found")
    previous = session.scalar(
        select(AutomationRunRecord).where(
            AutomationRunRecord.automation_id == automation.id,
            AutomationRunRecord.event_key == payload.event_key,
        )
    )
    if previous:
        return {"id": previous.id, "status": previous.status, "result": previous.result}
    item = get_work_item(session, actor, payload.entity_id)
    fields = {"priority": item.priority, "status": item.status, "type_code": item.type_code}
    matched = all(fields.get(key) == value for key, value in automation.conditions.items())
    executed: list[dict[str, object]] = []
    if matched:
        for action in automation.actions:
            action_type = action.get("type")
            if action_type == "set_priority" and action.get("value") in {
                "LOW",
                "NORMAL",
                "HIGH",
                "CRITICAL",
            }:
                item.priority = str(action["value"])
                executed.append(action)
            elif action_type == "notify":
                recipient_value = action.get("recipient", "assigned")
                recipient = item.assigned_to if recipient_value == "assigned" else item.created_by
                if recipient:
                    session.add(
                        NotificationRecord(
                            id=uuid4(),
                            organization_id=actor.organization_id,
                            recipient_id=recipient,
                            kind="AUTOMATION",
                            title=automation.name,
                            body=item.title,
                            entity_type="work_item",
                            entity_id=item.id,
                            read_at=None,
                            created_at=datetime.now(UTC),
                        )
                    )
                    executed.append(action)
    run = AutomationRunRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        automation_id=automation.id,
        entity_id=item.id,
        event_key=payload.event_key,
        status="COMPLETED",
        result={"matched": matched, "executed": executed},
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    session.add(run)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="automation.execute",
        entity_type="automation_run",
        entity_id=run.id,
        new_state=run.result,
    )
    session.commit()
    return {"id": run.id, "status": run.status, "result": run.result}
