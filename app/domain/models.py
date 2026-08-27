from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from app.domain.errors import ValidationError


def utc_now() -> datetime:
    return datetime.now(UTC)


class Priority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class WorkItemStatus(StrEnum):
    NEW = "NEW"
    ASSIGNED = "ASSIGNED"
    ACCEPTED = "ACCEPTED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"
    REVIEW = "REVIEW"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True, slots=True)
class DomainEvent:
    name: str
    aggregate_id: UUID
    organization_id: UUID
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class Organization:
    name: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if len(self.name) < 2:
            raise ValidationError("Organization name must contain at least 2 characters")


@dataclass(slots=True)
class WorkItem:
    organization_id: UUID
    title: str
    description: str
    type_code: str
    created_by: UUID
    priority: Priority = Priority.NORMAL
    id: UUID = field(default_factory=uuid4)
    human_readable_id: str | None = None
    status: str = WorkItemStatus.NEW
    assigned_to: UUID | None = None
    due_at: datetime | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    events: list[DomainEvent] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self.title = self.title.strip()
        self.description = self.description.strip()
        self.type_code = self.type_code.strip().upper()
        if not 3 <= len(self.title) <= 200:
            raise ValidationError("Title must contain between 3 and 200 characters")
        if not self.type_code:
            raise ValidationError("Work item type is required")
        if self.due_at is not None and self.due_at.tzinfo is None:
            raise ValidationError("Deadline must include a timezone")

    def mark_created(self) -> None:
        self.events.append(DomainEvent("WorkItemCreated", self.id, self.organization_id))

    def assign(self, member_id: UUID) -> None:
        self.assigned_to = member_id
        self.status = WorkItemStatus.ASSIGNED
        self.updated_at = utc_now()
        self.events.append(DomainEvent("WorkItemAssigned", self.id, self.organization_id))
