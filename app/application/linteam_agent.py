"""Channel-independent, deterministic LINTEAM Agent Phase 01 service."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.application.auth import ActorContext
from app.domain.models import WorkItemStatus
from app.infrastructure.database import (
    AgentConfirmationRecord,
    AssignmentRecord,
    CommentRecord,
    WorkItemRecord,
)
from app.infrastructure.sql_repositories import record_audit

OPEN = ["COMPLETED", "ARCHIVED", "CANCELLED"]


@dataclass(frozen=True, slots=True)
class AgentRequest:
    actor: ActorContext
    channel: str
    text: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class AgentResponse:
    text: str
    status: str = "OK"
    action: str = "READ"
    entity_id: UUID | None = None
    confirmation_id: str | None = None


class LinteamAgentService:
    """Keeps channel parsing outside the application-facing operational service."""

    def __init__(self, session: Session, app_base_url: str = "https://linteam.online"):
        self.session, self.app_base_url = session, app_base_url.rstrip("/")

    def execute(self, request: AgentRequest) -> AgentResponse:
        command, _, argument = request.text.strip().partition(" ")
        command = command.casefold()
        aliases = {
            "mis tareas": "/tasks",
            "tareas de hoy": "/today",
            "tareas atrasadas": "/overdue",
        }
        command = aliases.get(request.text.strip().casefold(), command)
        if command in {"/start", "/help", "help"}:
            return AgentResponse(
                "Comandos: /tasks, /today, /overdue, /task <id>, /done <id>, /comment <id> <texto>."
            )
        if command in {"/tasks", "/assigned"}:
            return self._list(request.actor, "Mis tareas")
        if command == "/today":
            return self._list(request.actor, "Tareas de hoy", due="today")
        if command == "/overdue":
            return self._list(request.actor, "Tareas atrasadas", due="overdue")
        if command == "/task":
            return self._detail(request.actor, argument)
        if command == "/done":
            return self._confirm_done(request, argument)
        if command == "/comment":
            task, sep, body = argument.partition(" ")
            if not sep or not body.strip():
                return AgentResponse("Usá: /comment <id> <comentario>", status="INVALID")
            return self._comment(request, task, body)
        if command == "/create":
            return AgentResponse(
                "Creá una tarea desde LINTEAM para completar responsable, fecha y confirmación.",
                status="NEEDS_WEB",
            )
        return AgentResponse("No entendí el comando. Usá /help.", status="UNKNOWN")

    def confirm(self, actor: ActorContext, channel: str, confirmation_id: str) -> AgentResponse:
        row = self.session.scalar(
            select(AgentConfirmationRecord).where(
                AgentConfirmationRecord.channel == channel,
                AgentConfirmationRecord.external_confirmation_id == confirmation_id,
                AgentConfirmationRecord.user_id == actor.user_id,
                AgentConfirmationRecord.organization_id == actor.organization_id,
            )
        )
        now = datetime.now(UTC)
        if row is None or row.consumed_at or row.expires_at <= now:
            return AgentResponse("Esta confirmación ya no es válida.", status="EXPIRED")
        item = self._item(actor, str(row.payload["work_item_id"]))
        current = WorkItemStatus(item.status)
        if WorkItemStatus.COMPLETED not in {
            WorkItemStatus.IN_PROGRESS: {WorkItemStatus.COMPLETED},
            WorkItemStatus.REVIEW: {WorkItemStatus.COMPLETED},
        }.get(current, set()):
            return AgentResponse(
                "La tarea no puede completarse desde su estado actual.", status="CONFLICT"
            )
        actor.require("workitem.update")
        item.status, item.updated_at, row.consumed_at = "COMPLETED", now, now
        record_audit(
            self.session,
            organization_id=actor.organization_id,
            actor_id=actor.user_id,
            action="agent.workitem.complete",
            entity_type="work_item",
            entity_id=item.id,
            new_state={"status": "COMPLETED", "channel": channel, "source": "LINTEAM_AGENT"},
        )
        self.session.commit()
        return AgentResponse(
            f"{item.human_readable_id} fue marcada como completada.",
            action="WRITE",
            entity_id=item.id,
        )

    def _items(self, actor: ActorContext):
        actor.require("workitem.view")
        return select(WorkItemRecord).where(
            WorkItemRecord.organization_id == actor.organization_id,
            or_(
                WorkItemRecord.assigned_to == actor.user_id,
                WorkItemRecord.created_by == actor.user_id,
                WorkItemRecord.id.in_(
                    select(AssignmentRecord.work_item_id).where(
                        AssignmentRecord.organization_id == actor.organization_id,
                        AssignmentRecord.assignee_id == actor.user_id,
                    )
                ),
            ),
            WorkItemRecord.status.notin_(OPEN),
        )

    def _list(self, actor: ActorContext, title: str, due: str | None = None) -> AgentResponse:
        query = self._items(actor)
        now = datetime.now(UTC)
        if due == "today":
            query = query.where(
                WorkItemRecord.due_at >= now.replace(hour=0, minute=0, second=0, microsecond=0),
                WorkItemRecord.due_at
                < now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
            )
        elif due == "overdue":
            query = query.where(WorkItemRecord.due_at < now)
        rows = self.session.scalars(
            query.order_by(WorkItemRecord.due_at.asc().nullslast()).limit(8)
        ).all()
        if not rows:
            return AgentResponse(f"{title}: no hay tareas pendientes.")
        lines = [f"{row.human_readable_id} · {row.title} ({row.status})" for row in rows]
        return AgentResponse(
            f"{title}\n" + "\n".join(lines) + f"\nVer todas: {self.app_base_url}/app/my-work"
        )

    def _item(self, actor: ActorContext, identifier: str) -> WorkItemRecord:
        query = self._items(actor)
        try:
            from uuid import UUID as ParsedUUID

            condition = WorkItemRecord.id == ParsedUUID(identifier)
        except ValueError:
            condition = WorkItemRecord.human_readable_id == identifier.upper()
        item = self.session.scalar(query.where(condition))
        if item is None:
            raise HTTPException(404, "Work item not found or not authorized")
        return item

    def _detail(self, actor: ActorContext, identifier: str) -> AgentResponse:
        if not identifier:
            return AgentResponse("Usá: /task <id>", status="INVALID")
        item = self._item(actor, identifier)
        due = item.due_at.isoformat() if item.due_at else "Sin fecha"
        return AgentResponse(
            f"{item.human_readable_id} · {item.title}\nEstado: {item.status}\nPrioridad: {item.priority}\nVence: {due}\n{self.app_base_url}/app/work/{item.id}",
            entity_id=item.id,
        )

    def _confirm_done(self, request: AgentRequest, identifier: str) -> AgentResponse:
        if not identifier:
            return AgentResponse("Usá: /done <id>", status="INVALID")
        item = self._item(request.actor, identifier)
        token = uuid4().hex
        self.session.add(
            AgentConfirmationRecord(
                id=uuid4(),
                organization_id=request.actor.organization_id,
                user_id=request.actor.user_id,
                channel=request.channel,
                external_confirmation_id=token,
                intent="COMPLETE_WORK_ITEM",
                payload={"work_item_id": str(item.id)},
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
                consumed_at=None,
                created_at=datetime.now(UTC),
            )
        )
        self.session.commit()
        return AgentResponse(
            f"¿Marcar '{item.title}' como completada?",
            status="CONFIRMATION_REQUIRED",
            action="WRITE",
            entity_id=item.id,
            confirmation_id=token,
        )

    def _comment(self, request: AgentRequest, identifier: str, body: str) -> AgentResponse:
        item = self._item(request.actor, identifier)
        request.actor.require("workitem.update")
        value = CommentRecord(
            id=uuid4(),
            organization_id=request.actor.organization_id,
            work_item_id=item.id,
            author_id=request.actor.user_id,
            body=body.strip(),
            internal=False,
            created_at=datetime.now(UTC),
        )
        self.session.add(value)
        record_audit(
            self.session,
            organization_id=request.actor.organization_id,
            actor_id=request.actor.user_id,
            action="agent.workitem.comment",
            entity_type="work_item",
            entity_id=item.id,
            new_state={"channel": request.channel, "source": "LINTEAM_AGENT"},
        )
        self.session.commit()
        return AgentResponse(
            f"Comentario agregado a {item.human_readable_id}.", action="WRITE", entity_id=item.id
        )
