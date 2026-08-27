from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from app.domain.models import Organization, WorkItem


class OrganizationRepository(Protocol):
    def add(self, organization: Organization) -> None: ...

    def get(self, organization_id: UUID) -> Organization | None: ...


class WorkItemRepository(Protocol):
    def next_reference(self, organization_id: UUID) -> str: ...

    def add(self, work_item: WorkItem) -> None: ...

    def get(self, organization_id: UUID, work_item_id: UUID) -> WorkItem | None: ...

    def list(self, organization_id: UUID) -> Sequence[WorkItem]: ...
