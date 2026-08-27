from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.errors import ConflictError
from app.domain.models import Organization, Priority, WorkItem
from app.infrastructure.database import (
    AuditEventRecord,
    OrganizationRecord,
    OutboxEventRecord,
    WorkItemRecord,
)


class SqlOrganizationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, organization: Organization) -> None:
        self.session.add(
            OrganizationRecord(
                id=organization.id,
                name=organization.name,
                created_at=organization.created_at,
            )
        )

    def get(self, organization_id: UUID) -> Organization | None:
        row = self.session.get(OrganizationRecord, organization_id)
        return Organization(row.name, row.id, row.created_at) if row else None


class SqlWorkItemRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def next_reference(self, organization_id: UUID) -> str:
        count = self.session.scalar(
            select(func.count())
            .select_from(WorkItemRecord)
            .where(WorkItemRecord.organization_id == organization_id)
        )
        return f"WI-{(count or 0) + 1:06d}"

    def add(self, item: WorkItem) -> None:
        if self.session.get(WorkItemRecord, item.id):
            raise ConflictError("Work item already exists")
        self.session.add(
            WorkItemRecord(
                id=item.id,
                organization_id=item.organization_id,
                human_readable_id=item.human_readable_id,
                title=item.title,
                description=item.description,
                type_code=item.type_code,
                status=item.status.value,
                priority=item.priority.value,
                created_by=item.created_by,
                assigned_to=item.assigned_to,
                due_at=item.due_at,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )

    def get(self, organization_id: UUID, work_item_id: UUID) -> WorkItem | None:
        row = self.session.scalar(
            select(WorkItemRecord).where(
                WorkItemRecord.id == work_item_id,
                WorkItemRecord.organization_id == organization_id,
            )
        )
        return self._to_domain(row) if row else None

    def list(self, organization_id: UUID) -> list[WorkItem]:
        rows = self.session.scalars(
            select(WorkItemRecord)
            .where(WorkItemRecord.organization_id == organization_id)
            .order_by(WorkItemRecord.created_at.desc())
        )
        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: WorkItemRecord) -> WorkItem:
        return WorkItem(
            organization_id=row.organization_id,
            title=row.title,
            description=row.description,
            type_code=row.type_code,
            created_by=row.created_by,
            priority=Priority(row.priority),
            id=row.id,
            human_readable_id=row.human_readable_id,
            status=row.status,
            assigned_to=row.assigned_to,
            due_at=row.due_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


def record_audit(
    session: Session,
    *,
    organization_id: UUID,
    actor_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: UUID,
    new_state: dict[str, object],
) -> None:
    session.add(
        AuditEventRecord(
            id=uuid4(),
            organization_id=organization_id,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            new_state=new_state,
            created_at=datetime.now(UTC),
        )
    )


def record_event(
    session: Session,
    *,
    organization_id: UUID,
    aggregate_type: str,
    aggregate_id: UUID,
    event_type: str,
    payload: dict[str, object],
) -> UUID:
    event_id = uuid4()
    occurred_at = datetime.now(UTC)
    session.add(
        OutboxEventRecord(
            id=event_id,
            organization_id=organization_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
            status="PENDING",
            attempts=0,
            occurred_at=occurred_at,
            published_at=None,
            next_attempt_at=occurred_at,
        )
    )
    return event_id
