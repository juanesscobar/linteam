from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.errors import ValidationError
from app.domain.models import WorkItem, WorkItemStatus


def test_work_item_normalizes_type_and_records_assignment() -> None:
    item = WorkItem(uuid4(), "  Solicitar compra  ", "Equipo", "purchase_request", uuid4())

    assignee = uuid4()
    item.assign(assignee)

    assert item.title == "Solicitar compra"
    assert item.type_code == "PURCHASE_REQUEST"
    assert item.assigned_to == assignee
    assert item.status is WorkItemStatus.ASSIGNED
    assert item.events[-1].name == "WorkItemAssigned"


def test_work_item_rejects_naive_deadline() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        WorkItem(uuid4(), "Valid title", "", "TASK", uuid4(), due_at=datetime(2030, 1, 1))


def test_work_item_accepts_utc_deadline() -> None:
    item = WorkItem(
        uuid4(), "Valid title", "", "TASK", uuid4(), due_at=datetime(2030, 1, 1, tzinfo=UTC)
    )
    assert item.due_at is not None
