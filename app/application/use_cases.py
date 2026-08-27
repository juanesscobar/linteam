from dataclasses import dataclass
from datetime import datetime

from app.application.auth import ActorContext
from app.application.ports import OrganizationRepository, WorkItemRepository
from app.domain.errors import NotFoundError
from app.domain.models import Organization, Priority, WorkItem


@dataclass(frozen=True, slots=True)
class CreateOrganization:
    organizations: OrganizationRepository

    def execute(self, name: str) -> Organization:
        organization = Organization(name=name)
        self.organizations.add(organization)
        return organization


@dataclass(frozen=True, slots=True)
class CreateWorkItem:
    organizations: OrganizationRepository
    work_items: WorkItemRepository

    def execute(
        self,
        actor: ActorContext,
        *,
        title: str,
        description: str,
        type_code: str,
        priority: Priority = Priority.NORMAL,
        due_at: datetime | None = None,
    ) -> WorkItem:
        actor.require("workitem.create")
        if self.organizations.get(actor.organization_id) is None:
            raise NotFoundError("Organization not found")
        work_item = WorkItem(
            organization_id=actor.organization_id,
            title=title,
            description=description,
            type_code=type_code,
            created_by=actor.user_id,
            priority=priority,
            due_at=due_at,
        )
        work_item.human_readable_id = self.work_items.next_reference(actor.organization_id)
        work_item.mark_created()
        self.work_items.add(work_item)
        return work_item


@dataclass(frozen=True, slots=True)
class ListWorkItems:
    work_items: WorkItemRepository

    def execute(self, actor: ActorContext) -> list[WorkItem]:
        actor.require("workitem.view")
        return list(self.work_items.list(actor.organization_id))
