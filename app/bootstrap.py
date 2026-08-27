from dataclasses import dataclass

from app.application.use_cases import CreateOrganization, CreateWorkItem, ListWorkItems
from app.infrastructure.memory import InMemoryOrganizationRepository, InMemoryWorkItemRepository


@dataclass(frozen=True, slots=True)
class Container:
    create_organization: CreateOrganization
    create_work_item: CreateWorkItem
    list_work_items: ListWorkItems


def build_container() -> Container:
    organizations = InMemoryOrganizationRepository()
    work_items = InMemoryWorkItemRepository()
    return Container(
        create_organization=CreateOrganization(organizations),
        create_work_item=CreateWorkItem(organizations, work_items),
        list_work_items=ListWorkItems(work_items),
    )
