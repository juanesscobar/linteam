from collections import defaultdict
from threading import Lock
from uuid import UUID

from app.domain.errors import ConflictError
from app.domain.models import Organization, WorkItem


class InMemoryOrganizationRepository:
    def __init__(self) -> None:
        self._items: dict[UUID, Organization] = {}

    def add(self, organization: Organization) -> None:
        if organization.id in self._items:
            raise ConflictError("Organization already exists")
        self._items[organization.id] = organization

    def get(self, organization_id: UUID) -> Organization | None:
        return self._items.get(organization_id)


class InMemoryWorkItemRepository:
    def __init__(self) -> None:
        self._items: dict[UUID, WorkItem] = {}
        self._sequences: defaultdict[UUID, int] = defaultdict(int)
        self._lock = Lock()

    def next_reference(self, organization_id: UUID) -> str:
        with self._lock:
            self._sequences[organization_id] += 1
            return f"WI-{self._sequences[organization_id]:06d}"

    def add(self, work_item: WorkItem) -> None:
        if work_item.id in self._items:
            raise ConflictError("Work item already exists")
        self._items[work_item.id] = work_item

    def get(self, organization_id: UUID, work_item_id: UUID) -> WorkItem | None:
        item = self._items.get(work_item_id)
        return item if item and item.organization_id == organization_id else None

    def list(self, organization_id: UUID) -> list[WorkItem]:
        return [item for item in self._items.values() if item.organization_id == organization_id]
