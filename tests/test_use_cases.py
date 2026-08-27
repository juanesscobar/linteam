from uuid import uuid4

import pytest

from app.application.auth import ActorContext
from app.application.use_cases import CreateOrganization, CreateWorkItem, ListWorkItems
from app.domain.errors import AuthorizationError
from app.infrastructure.memory import InMemoryOrganizationRepository, InMemoryWorkItemRepository


def test_list_is_isolated_by_organization() -> None:
    organizations = InMemoryOrganizationRepository()
    work_items = InMemoryWorkItemRepository()
    create_org = CreateOrganization(organizations)
    create_item = CreateWorkItem(organizations, work_items)
    list_items = ListWorkItems(work_items)
    first = create_org.execute("Lin Group")
    second = create_org.execute("Other Group")
    first_actor = ActorContext(uuid4(), first.id, frozenset({"workitem.create", "workitem.view"}))
    second_actor = ActorContext(uuid4(), second.id, frozenset({"workitem.view"}))

    create_item.execute(first_actor, title="Prepare report", description="", type_code="TASK")

    assert len(list_items.execute(first_actor)) == 1
    assert list_items.execute(second_actor) == []


def test_create_requires_server_side_permission() -> None:
    organizations = InMemoryOrganizationRepository()
    organization = CreateOrganization(organizations).execute("Lin Group")
    use_case = CreateWorkItem(organizations, InMemoryWorkItemRepository())
    actor = ActorContext(uuid4(), organization.id, frozenset())

    with pytest.raises(AuthorizationError, match="workitem.create"):
        use_case.execute(actor, title="Prepare report", description="", type_code="TASK")
