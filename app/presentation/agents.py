import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.application.auth import ActorContext
from app.infrastructure.database import (
    AgentActionProposalRecord,
    AgentApiTokenRecord,
    AgentApprovalRecord,
    AgentCapabilityRecord,
    AgentPermissionRecord,
    AgentRecord,
    AgentRunRecord,
    DepartmentRecord,
    NotificationRecord,
    ProcessRecommendationRecord,
    WorkItemRecord,
    get_session,
)
from app.infrastructure.sql_repositories import record_audit
from app.presentation.auth import current_actor


class AgentInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=500)
    risk_level: Literal["LOW", "MEDIUM", "HIGH"] = "LOW"
    capabilities: list[str] = Field(min_length=1, max_length=50)
    permissions: list[str] = Field(default_factory=list, max_length=100)


class AskInput(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class ClassifyInput(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=5000)


class ProposalInput(BaseModel):
    agent_run_id: UUID
    action_type: Literal["set_priority", "notify"]
    target_id: UUID
    arguments: dict[str, object]
    risk_level: Literal["LOW", "MEDIUM", "HIGH"] = "LOW"
    rationale: str = Field(min_length=3, max_length=1000)


class ProposalDecision(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    comment: str = Field(default="", max_length=1000)


class AgentTokenInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    scopes: list[Literal["runs.read", "runs.write"]] = Field(min_length=1, max_length=2)
    expires_in_days: int | None = Field(default=90, ge=1, le=365)


class AgentRunInput(BaseModel):
    capability: str = Field(min_length=2, max_length=100)
    input: dict[str, object] = Field(default_factory=dict)


class AgentRunCompletion(BaseModel):
    output: dict[str, object] = Field(default_factory=dict)
    status: Literal["COMPLETED", "FAILED"] = "COMPLETED"


router = APIRouter(prefix="/api/v1")


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def authenticated_agent(
    session: Session,
    value: str | None,
    required_scope: str,
) -> tuple[AgentRecord, AgentApiTokenRecord]:
    if not value or not value.startswith("lta_"):
        raise HTTPException(401, "Missing or invalid agent token")
    record = session.scalar(
        select(AgentApiTokenRecord).where(AgentApiTokenRecord.token_hash == token_hash(value))
    )
    now = datetime.now(UTC)
    if (
        record is None
        or record.revoked_at is not None
        or (record.expires_at is not None and record.expires_at <= now)
        or required_scope not in record.scopes
    ):
        raise HTTPException(401, "Agent token is not authorized")
    agent = session.scalar(
        select(AgentRecord).where(
            AgentRecord.id == record.agent_id,
            AgentRecord.organization_id == record.organization_id,
            AgentRecord.active.is_(True),
        )
    )
    if agent is None:
        raise HTTPException(403, "Agent is inactive")
    record.last_used_at = now
    return agent, record


@router.post("/agents", status_code=201)
def create_agent(
    payload: AgentInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("agent.manage")
    agent = AgentRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        active=True,
        risk_level=payload.risk_level,
        created_at=datetime.now(UTC),
    )
    session.add(agent)
    session.flush()
    session.add_all(
        [
            AgentCapabilityRecord(id=uuid4(), agent_id=agent.id, code=code, description="")
            for code in sorted(set(payload.capabilities))
        ]
    )
    session.add_all(
        [
            AgentPermissionRecord(id=uuid4(), agent_id=agent.id, permission_code=code)
            for code in sorted(set(payload.permissions))
        ]
    )
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="agent.create",
        entity_type="agent",
        entity_id=agent.id,
        new_state={"name": agent.name, "capabilities": payload.capabilities},
    )
    session.commit()
    return {"id": agent.id, "name": agent.name, "active": agent.active}


@router.post("/agents/{agent_id}/tokens", status_code=201)
def create_agent_token(
    agent_id: UUID,
    payload: AgentTokenInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("agent.manage")
    agent = session.scalar(
        select(AgentRecord).where(
            AgentRecord.id == agent_id, AgentRecord.organization_id == actor.organization_id
        )
    )
    if agent is None:
        raise HTTPException(404, "Agent not found")
    raw_token = f"lta_{secrets.token_urlsafe(32)}"
    now = datetime.now(UTC)
    record = AgentApiTokenRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        agent_id=agent.id,
        name=payload.name.strip(),
        token_prefix=raw_token[:20],
        token_hash=token_hash(raw_token),
        scopes=sorted(set(payload.scopes)),
        expires_at=now + timedelta(days=payload.expires_in_days)
        if payload.expires_in_days
        else None,
        revoked_at=None,
        last_used_at=None,
        created_at=now,
    )
    session.add(record)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="agent.token.create",
        entity_type="agent_token",
        entity_id=record.id,
        new_state={"agent_id": str(agent.id), "scopes": record.scopes},
    )
    session.commit()
    return {
        "id": record.id,
        "name": record.name,
        "token": raw_token,
        "expires_at": record.expires_at,
        "scopes": record.scopes,
    }


@router.get("/agents/{agent_id}/tokens")
def list_agent_tokens(
    agent_id: UUID,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> list[dict[str, object]]:
    actor.require("agent.manage")
    return [
        {
            "id": row.id,
            "name": row.name,
            "prefix": row.token_prefix,
            "scopes": row.scopes,
            "expires_at": row.expires_at,
            "revoked_at": row.revoked_at,
            "last_used_at": row.last_used_at,
        }
        for row in session.scalars(
            select(AgentApiTokenRecord)
            .where(
                AgentApiTokenRecord.agent_id == agent_id,
                AgentApiTokenRecord.organization_id == actor.organization_id,
            )
            .order_by(AgentApiTokenRecord.created_at.desc())
        ).all()
    ]


@router.delete("/agents/{agent_id}/tokens/{token_id}", status_code=204)
def revoke_agent_token(
    agent_id: UUID,
    token_id: UUID,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    actor.require("agent.manage")
    record = session.scalar(
        select(AgentApiTokenRecord).where(
            AgentApiTokenRecord.id == token_id,
            AgentApiTokenRecord.agent_id == agent_id,
            AgentApiTokenRecord.organization_id == actor.organization_id,
        )
    )
    if record is None:
        raise HTTPException(404, "Agent token not found")
    record.revoked_at = datetime.now(UTC)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="agent.token.revoke",
        entity_type="agent_token",
        entity_id=record.id,
        new_state={"revoked": True},
    )
    session.commit()


@router.post("/agents/{agent_id}/runs", status_code=202)
def queue_agent_run(
    agent_id: UUID,
    payload: AgentRunInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("agent.propose")
    agent = session.scalar(
        select(AgentRecord)
        .join(AgentCapabilityRecord)
        .where(
            AgentRecord.id == agent_id,
            AgentRecord.organization_id == actor.organization_id,
            AgentRecord.active.is_(True),
            AgentCapabilityRecord.code == payload.capability,
        )
    )
    if agent is None:
        raise HTTPException(404, "Active agent or capability not found")
    now = datetime.now(UTC)
    run = AgentRunRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        agent_id=agent.id,
        requested_by=actor.user_id,
        capability=payload.capability,
        input_summary=f"sha256:{hashlib.sha256(repr(sorted(payload.input.items())).encode()).hexdigest()}",
        output={"input": payload.input},
        status="PENDING",
        started_at=now,
        finished_at=None,
    )
    session.add(run)
    session.commit()
    return {"id": run.id, "status": run.status}


@router.get("/agent-gateway/jobs/next")
def next_agent_job(
    x_agent_token: Annotated[str | None, Header()] = None,
    session: Annotated[Session, Depends(get_session)] = None,
) -> dict[str, object] | None:
    agent, _token = authenticated_agent(session, x_agent_token, "runs.read")
    run = session.scalar(
        select(AgentRunRecord)
        .where(
            AgentRunRecord.agent_id == agent.id,
            AgentRunRecord.organization_id == agent.organization_id,
            AgentRunRecord.status == "PENDING",
        )
        .order_by(AgentRunRecord.started_at)
    )
    if run is None:
        session.commit()
        return None
    run.status = "RUNNING"
    session.commit()
    return {"id": run.id, "capability": run.capability, "input": run.output.get("input", {})}


@router.post("/agent-gateway/jobs/{run_id}/complete")
def complete_agent_job(
    run_id: UUID,
    payload: AgentRunCompletion,
    x_agent_token: Annotated[str | None, Header()] = None,
    session: Annotated[Session, Depends(get_session)] = None,
) -> dict[str, object]:
    agent, _token = authenticated_agent(session, x_agent_token, "runs.write")
    run = session.scalar(
        select(AgentRunRecord).where(
            AgentRunRecord.id == run_id,
            AgentRunRecord.agent_id == agent.id,
            AgentRunRecord.organization_id == agent.organization_id,
        )
    )
    if run is None:
        raise HTTPException(404, "Agent run not found")
    if run.status != "RUNNING":
        raise HTTPException(409, "Agent run is not running")
    run.output, run.status, run.finished_at = payload.output, payload.status, datetime.now(UTC)
    session.commit()
    return {"id": run.id, "status": run.status}


def route_agent(session: Session, organization_id: UUID, capability: str) -> AgentRecord:
    agent = session.scalar(
        select(AgentRecord)
        .join(AgentCapabilityRecord, AgentCapabilityRecord.agent_id == AgentRecord.id)
        .where(
            AgentRecord.organization_id == organization_id,
            AgentRecord.active.is_(True),
            AgentCapabilityRecord.code == capability,
        )
        .order_by(AgentRecord.created_at)
    )
    if agent is None:
        raise HTTPException(503, f"No active agent supports {capability}")
    return agent


@router.post("/ask-conciencia")
def ask_conciencia(
    payload: AskInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("workitem.view")
    agent = route_agent(session, actor.organization_id, "organizational_query")
    question = payload.question.casefold()
    base = WorkItemRecord.organization_id == actor.organization_id
    if any(word in question for word in ("vencid", "overdue")):
        now = datetime.now(UTC)
        count = (
            session.scalar(
                select(func.count())
                .select_from(WorkItemRecord)
                .where(
                    base,
                    WorkItemRecord.due_at < now,
                    WorkItemRecord.status.notin_(["COMPLETED", "ARCHIVED", "CANCELLED"]),
                )
            )
            or 0
        )
        output = {"intent": "overdue", "count": count, "answer": f"Hay {count} trabajos vencidos."}
    elif any(word in question for word in ("estado", "status", "resumen")):
        rows = session.execute(
            select(WorkItemRecord.status, func.count()).where(base).group_by(WorkItemRecord.status)
        ).all()
        counts = {status: count for status, count in rows}
        output = {
            "intent": "status_summary",
            "counts": counts,
            "answer": f"Resumen por estado: {counts}",
        }
    else:
        terms = f"%{payload.question.strip()[:100]}%"
        matches = session.scalars(
            select(WorkItemRecord)
            .where(
                base,
                or_(
                    WorkItemRecord.title.ilike(terms), WorkItemRecord.human_readable_id.ilike(terms)
                ),
            )
            .limit(10)
        ).all()
        output = {
            "intent": "search",
            "matches": [
                {"id": str(item.id), "reference": item.human_readable_id, "title": item.title}
                for item in matches
            ],
            "answer": f"Encontré {len(matches)} coincidencias.",
        }
    now = datetime.now(UTC)
    run = AgentRunRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        agent_id=agent.id,
        requested_by=actor.user_id,
        capability="organizational_query",
        input_summary=f"sha256:{hashlib.sha256(payload.question.encode()).hexdigest()}",
        output=output,
        status="COMPLETED",
        started_at=now,
        finished_at=now,
    )
    session.add(run)
    session.commit()
    return {"run_id": run.id, "agent": agent.name, **output}


@router.post("/conciencia/classify")
def classify_work(
    payload: ClassifyInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("workitem.create")
    agent = route_agent(session, actor.organization_id, "classification")
    text = f"{payload.title} {payload.description}".casefold()
    rules = [
        (("contrato", "legal", "demanda"), "LEGAL_REQUEST", ("legal",)),
        (
            ("computadora", "internet", "sistema", "password"),
            "IT_REQUEST",
            ("tecnolog", "information"),
        ),
        (("comprar", "compra", "cotización"), "PURCHASE_REQUEST", ("compra", "purchas")),
        (("cobro", "deuda", "pago"), "COLLECTION_CASE", ("cobran", "collection")),
        (("vacaciones", "empleado", "nómina"), "HR_REQUEST", ("human", "recursos")),
    ]
    suggested_type, department_terms, confidence = "REQUEST", (), 0.35
    for keywords, type_code, terms in rules:
        if any(keyword in text for keyword in keywords):
            suggested_type, department_terms, confidence = type_code, terms, 0.8
            break
    departments = session.scalars(
        select(DepartmentRecord).where(
            DepartmentRecord.organization_id == actor.organization_id,
            DepartmentRecord.archived_at.is_(None),
        )
    ).all()
    department = next(
        (
            item
            for item in departments
            if any(term in item.name.casefold() for term in department_terms)
        ),
        None,
    )
    output = {
        "suggested_type": suggested_type,
        "suggested_department_id": str(department.id) if department else None,
        "suggested_department": department.name if department else None,
        "confidence": confidence,
        "requires_human_confirmation": True,
    }
    now = datetime.now(UTC)
    run = AgentRunRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        agent_id=agent.id,
        requested_by=actor.user_id,
        capability="classification",
        input_summary=f"sha256:{hashlib.sha256(text.encode()).hexdigest()}",
        output=output,
        status="COMPLETED",
        started_at=now,
        finished_at=now,
    )
    session.add(run)
    session.commit()
    return {"run_id": run.id, "agent": agent.name, **output}


@router.get("/search")
def search(
    query: str,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
    limit: int = 20,
) -> list[dict[str, object]]:
    actor.require("workitem.view")
    pattern = f"%{query.strip()[:100]}%"
    items = session.scalars(
        select(WorkItemRecord)
        .where(
            WorkItemRecord.organization_id == actor.organization_id,
            or_(
                WorkItemRecord.title.ilike(pattern),
                WorkItemRecord.description.ilike(pattern),
                WorkItemRecord.human_readable_id.ilike(pattern),
            ),
        )
        .limit(min(max(limit, 1), 100))
    ).all()
    return [
        {
            "id": item.id,
            "reference": item.human_readable_id,
            "title": item.title,
            "status": item.status,
        }
        for item in items
    ]


@router.post("/agent-proposals", status_code=201)
def propose_action(
    payload: ProposalInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("agent.propose")
    run = session.scalar(
        select(AgentRunRecord).where(
            AgentRunRecord.id == payload.agent_run_id,
            AgentRunRecord.organization_id == actor.organization_id,
        )
    )
    target = session.scalar(
        select(WorkItemRecord).where(
            WorkItemRecord.id == payload.target_id,
            WorkItemRecord.organization_id == actor.organization_id,
        )
    )
    if run is None or target is None:
        raise HTTPException(404, "Agent run or target not found")
    proposal = AgentActionProposalRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        agent_run_id=run.id,
        proposed_by=actor.user_id,
        action_type=payload.action_type,
        target_type="work_item",
        target_id=target.id,
        arguments=payload.arguments,
        risk_level=payload.risk_level,
        rationale=payload.rationale.strip(),
        status="PENDING",
        created_at=datetime.now(UTC),
        executed_at=None,
    )
    session.add(proposal)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="agent.proposal.create",
        entity_type="agent_proposal",
        entity_id=proposal.id,
        new_state={"status": "PENDING", "action": proposal.action_type},
    )
    session.commit()
    return {"id": proposal.id, "status": proposal.status, "risk_level": proposal.risk_level}


@router.post("/agent-proposals/{proposal_id}/decision")
def decide_proposal(
    proposal_id: UUID,
    payload: ProposalDecision,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("agent.approve")
    proposal = session.scalar(
        select(AgentActionProposalRecord).where(
            AgentActionProposalRecord.id == proposal_id,
            AgentActionProposalRecord.organization_id == actor.organization_id,
        )
    )
    if proposal is None:
        raise HTTPException(404, "Proposal not found")
    if proposal.status != "PENDING":
        raise HTTPException(409, "Proposal already decided")
    approval = AgentApprovalRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        proposal_id=proposal.id,
        decided_by=actor.user_id,
        decision=payload.decision,
        comment=payload.comment.strip(),
        decided_at=datetime.now(UTC),
    )
    proposal.status = payload.decision
    session.add(approval)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="agent.proposal.decide",
        entity_type="agent_proposal",
        entity_id=proposal.id,
        new_state={"status": proposal.status},
    )
    session.commit()
    return {"id": proposal.id, "status": proposal.status}


@router.post("/agent-proposals/{proposal_id}/execute")
def execute_proposal(
    proposal_id: UUID,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("agent.execute")
    proposal = session.scalar(
        select(AgentActionProposalRecord).where(
            AgentActionProposalRecord.id == proposal_id,
            AgentActionProposalRecord.organization_id == actor.organization_id,
        )
    )
    if proposal is None:
        raise HTTPException(404, "Proposal not found")
    if proposal.status == "EXECUTED":
        return {"id": proposal.id, "status": proposal.status, "duplicate": True}
    if proposal.status != "APPROVED":
        raise HTTPException(409, "Human approval is required")
    target = session.scalar(
        select(WorkItemRecord).where(
            WorkItemRecord.id == proposal.target_id,
            WorkItemRecord.organization_id == actor.organization_id,
        )
    )
    if target is None:
        raise HTTPException(404, "Target not found")
    if proposal.action_type == "set_priority":
        value = proposal.arguments.get("priority")
        if value not in {"LOW", "NORMAL", "HIGH", "CRITICAL"}:
            raise HTTPException(422, "Invalid proposed priority")
        target.priority = str(value)
    elif proposal.action_type == "notify":
        recipient = target.assigned_to or target.created_by
        session.add(
            NotificationRecord(
                id=uuid4(),
                organization_id=actor.organization_id,
                recipient_id=recipient,
                kind="AGENT_RECOMMENDATION",
                title="Recomendación aprobada",
                body=proposal.rationale[:500],
                entity_type="work_item",
                entity_id=target.id,
                read_at=None,
                created_at=datetime.now(UTC),
            )
        )
    proposal.status, proposal.executed_at = "EXECUTED", datetime.now(UTC)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="agent.proposal.execute",
        entity_type="agent_proposal",
        entity_id=proposal.id,
        new_state={"status": "EXECUTED"},
    )
    session.commit()
    return {"id": proposal.id, "status": proposal.status, "duplicate": False}


@router.post("/jobs/process-intelligence")
def process_intelligence(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("system.jobs")
    rows = session.execute(
        select(WorkItemRecord.status, func.count())
        .where(WorkItemRecord.organization_id == actor.organization_id)
        .group_by(WorkItemRecord.status)
    ).all()
    counts = {status: count for status, count in rows}
    generated: list[UUID] = []
    blocked = counts.get("BLOCKED", 0) + counts.get("WAITING", 0)
    if blocked:
        recommendation = ProcessRecommendationRecord(
            id=uuid4(),
            organization_id=actor.organization_id,
            kind="BOTTLENECK",
            title="Trabajo bloqueado o en espera",
            evidence={"blocked_or_waiting": blocked, "status_counts": counts},
            recommendation="Revisar responsables y dependencias antes de modificar el workflow.",
            status="OPEN",
            generated_at=datetime.now(UTC),
        )
        session.add(recommendation)
        generated.append(recommendation.id)
    session.commit()
    return {"generated": len(generated), "recommendation_ids": generated, "evidence": counts}
