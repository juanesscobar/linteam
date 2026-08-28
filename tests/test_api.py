import hashlib
import hmac
import json
import time
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database import Base, get_session
from app.main import app
from app.settings import Settings, get_settings


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    def override() -> Generator[Session, None, None]:
        with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override
    app.dependency_overrides[get_settings] = lambda: Settings(
        file_storage_path=str(tmp_path / "files")
    )
    with TestClient(app) as value:
        yield value
    app.dependency_overrides.clear()


def test_invited_member_can_join_and_then_log_in_without_organization_id(client: TestClient) -> None:
    setup = client.post(
        "/api/v1/setup",
        headers={"X-Bootstrap-Token": "development-bootstrap-token"},
        json={
            "organization_name": "Lin Group",
            "organization_code": "LINTEAM",
            "admin_name": "Admin",
            "admin_email": "admin@linteam.example.com",
            "password": "very-secure-password",
        },
    )
    assert setup.status_code == 201
    assert setup.json()["code"] == "LINTEAM"
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@linteam.example.com", "password": "very-secure-password"},
    )
    assert admin_login.status_code == 200
    invitation = client.post(
        "/api/v1/invitations",
        headers={"Authorization": f"Bearer {admin_login.json()['access_token']}"},
        json={"email": "member@lingroup.example.com"},
    )
    assert invitation.status_code == 201
    joined = client.post(
        "/api/v1/auth/join",
        json={
            "organization_code": "LINTEAM",
            "invitation_token": invitation.json()["invitation_token"],
            "name": "Miembro Lin Group",
            "email": "member@lingroup.example.com",
            "password": "member-secure-password",
        },
    )
    assert joined.status_code == 201
    member_login = client.post(
        "/api/v1/auth/login",
        json={"email": "member@lingroup.example.com", "password": "member-secure-password"},
    )
    assert member_login.status_code == 200
    assert (
        client.post(
            "/api/v1/auth/join",
            json={
                "organization_code": "LINTEAM",
                "invitation_token": invitation.json()["invitation_token"],
                "name": "Otra Persona",
                "email": "member@lingroup.example.com",
                "password": "another-secure-password",
            },
        ).status_code
        == 403
    )


def test_authenticated_end_to_end_flow(client: TestClient) -> None:
    payload = {
        "organization_name": "Lin Group",
        "admin_name": "Admin",
        "admin_email": "admin@linteam.example.com",
        "password": "very-secure-password",
    }
    setup = client.post(
        "/api/v1/setup", headers={"X-Bootstrap-Token": "development-bootstrap-token"}, json=payload
    )
    assert setup.status_code == 201
    assert (
        client.post(
            "/api/v1/setup",
            headers={"X-Bootstrap-Token": "development-bootstrap-token"},
            json=payload,
        ).status_code
        == 409
    )
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@linteam.example.com",
            "password": "very-secure-password",
            "organization_id": setup.json()["id"],
        },
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    rotated = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login.json()["refresh_token"]}
    )
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != login.json()["refresh_token"]
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": login.json()["refresh_token"]}
        ).status_code
        == 401
    )
    department = client.post("/api/v1/departments", headers=headers, json={"name": "Legal"})
    assert department.status_code == 201
    team = client.post(
        "/api/v1/teams",
        headers=headers,
        json={"name": "Contracts", "department_id": department.json()["id"]},
    )
    assert team.status_code == 201
    role = client.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "name": "Legal reviewer",
            "permissions": ["workitem.create", "workitem.view", "workitem.update"],
        },
    )
    assert role.status_code == 201
    member = client.post(
        "/api/v1/members",
        headers=headers,
        json={
            "name": "Reviewer",
            "email": "reviewer@linteam.example.com",
            "password": "another-secure-password",
            "department_id": department.json()["id"],
            "team_id": team.json()["id"],
            "role_ids": [role.json()["id"]],
        },
    )
    assert member.status_code == 201
    profile = client.put(
        f"/api/v1/members/{member.json()['id']}",
        headers=headers,
        json={
            "job_title": "Legal reviewer",
            "department_id": department.json()["id"],
            "team_id": team.json()["id"],
            "phone": "+595000000",
            "responsibilities": ["Revisar contratos"],
            "specialties": ["Derecho comercial"],
        },
    )
    assert profile.status_code == 200
    assert profile.json()["operational"]["active_assignments"] == 0
    assert (
        client.put(
            "/api/v1/me/notification-preferences",
            headers=headers,
            json={"event_type": "ASSIGNMENT", "channels": ["IN_APP", "TELEGRAM"]},
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/api/v1/configuration/business-units",
            headers=headers,
            json={"name": "Corporate Services"},
        ).status_code
        == 201
    )
    work_type = client.post(
        "/api/v1/configuration/work-item-types",
        headers=headers,
        json={"code": "LEGAL_REQUEST", "name": "Solicitud legal"},
    )
    tag = client.post(
        "/api/v1/configuration/tags",
        headers=headers,
        json={"name": "Contrato", "color": "#12372a"},
    )
    custom_field = client.post(
        "/api/v1/configuration/custom-fields",
        headers=headers,
        json={"key": "contract_value", "name": "Valor", "field_type": "NUMBER"},
    )
    assert work_type.status_code == tag.status_code == custom_field.status_code == 201
    created = client.post(
        "/api/v1/work-items",
        headers=headers,
        json={
            "title": "Revisar contrato",
            "type_code": "LEGAL_REQUEST",
            "priority": "CRITICAL",
            "impact": "LEGAL",
            "expected_deliverable": "Informe legal aprobado",
            "tag_ids": [tag.json()["id"]],
            "custom_fields": {"contract_value": 1200.5},
        },
    )
    assert created.status_code == 201
    assert created.json()["human_readable_id"] == "WI-000001"
    assert client.post("/api/v1/jobs/outbox-publish", headers=headers).json() == {
        "published": 1,
        "retried": 0,
    }
    work_item_id = created.json()["id"]
    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "Contratos 2026",
            "owner_id": member.json()["user_id"],
            "department_id": department.json()["id"],
        },
    )
    assert project.status_code == 201
    assert (
        client.post(
            f"/api/v1/projects/{project.json()['id']}/work-items",
            headers=headers,
            json={"work_item_id": work_item_id},
        ).status_code
        == 204
    )
    detail = client.get(f"/api/v1/projects/{project.json()['id']}", headers=headers)
    assert detail.json()["work_items"] == 1
    assigned = client.post(
        f"/api/v1/work-items/{work_item_id}/assign",
        headers=headers,
        json={"assignee_id": member.json()["user_id"]},
    )
    assert assigned.status_code == 204
    reviewer_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "reviewer@linteam.example.com",
            "password": "another-secure-password",
            "organization_id": setup.json()["id"],
        },
    )
    reviewer_headers = {"Authorization": f"Bearer {reviewer_login.json()['access_token']}"}
    notifications = client.get("/api/v1/notifications", headers=reviewer_headers)
    assert len(notifications.json()) == 1
    accepted = client.post(
        f"/api/v1/work-items/{work_item_id}/status",
        headers=reviewer_headers,
        json={"status": "ACCEPTED"},
    )
    assert accepted.status_code == 204
    assert (
        client.post(
            f"/api/v1/work-items/{work_item_id}/comments",
            headers=reviewer_headers,
            json={"body": "Contrato recibido"},
        ).status_code
        == 201
    )
    checklist = client.post(
        f"/api/v1/work-items/{work_item_id}/checklists",
        headers=reviewer_headers,
        json={"title": "Revisión", "items": ["Validar firmas", "Validar monto"]},
    )
    assert checklist.status_code == 201
    assert len(checklist.json()) == 2
    toggled = client.post(
        f"/api/v1/checklist-items/{checklist.json()[0]['id']}/toggle",
        headers=reviewer_headers,
    )
    assert toggled.json()["completed"] is True
    attachment = client.post(
        f"/api/v1/work-items/{work_item_id}/attachments",
        headers=reviewer_headers,
        files={"file": ("contrato.txt", b"contenido privado", "text/plain")},
    )
    assert attachment.status_code == 201
    downloaded = client.get(
        f"/api/v1/attachments/{attachment.json()['id']}/content",
        headers=reviewer_headers,
    )
    assert downloaded.content == b"contenido privado"
    assert len(client.get("/api/v1/my-work", headers=reviewer_headers).json()) == 1
    summary = client.get("/api/v1/analytics/executive", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["total"] == 1
    workflow = client.post(
        "/api/v1/workflows",
        headers=headers,
        json={
            "name": "Legal",
            "activate": True,
            "states": [
                {"code": "NEW", "name": "Nuevo", "initial": True},
                {"code": "REVIEW", "name": "Revisión"},
                {"code": "DONE", "name": "Finalizado", "terminal": True},
            ],
            "transitions": [
                {"from_code": "NEW", "to_code": "REVIEW"},
                {"from_code": "REVIEW", "to_code": "DONE", "requires_approval": True},
            ],
        },
    )
    assert workflow.status_code == 201
    assert (
        client.post(
            f"/api/v1/work-items/{work_item_id}/workflow",
            headers=headers,
            json={"workflow_id": workflow.json()["id"]},
        ).status_code
        == 204
    )
    assert (
        client.post(
            f"/api/v1/work-items/{work_item_id}/workflow-transition",
            headers=headers,
            json={"to_code": "REVIEW"},
        ).status_code
        == 204
    )
    assert (
        client.post(
            f"/api/v1/work-items/{work_item_id}/workflow-transition",
            headers=headers,
            json={"to_code": "DONE"},
        ).status_code
        == 409
    )
    approval = client.post(
        f"/api/v1/work-items/{work_item_id}/approvals",
        headers=headers,
        json={
            "requested_from": member.json()["user_id"],
            "reason": "Validar resultado",
            "amount": "1200.50",
        },
    )
    assert approval.status_code == 201
    decision = client.post(
        f"/api/v1/approvals/{approval.json()['id']}/decision",
        headers=reviewer_headers,
        json={"decision": "APPROVED", "comment": "Conforme"},
    )
    assert decision.json()["status"] == "APPROVED"
    assert (
        client.post(
            f"/api/v1/work-items/{work_item_id}/workflow-transition",
            headers=headers,
            json={"to_code": "DONE"},
        ).status_code
        == 204
    )
    deliverable = client.post(
        f"/api/v1/work-items/{work_item_id}/deliverables",
        headers=reviewer_headers,
        json={"kind": "TEXT", "content": "Informe legal final"},
    )
    assert deliverable.status_code == 201
    reviewed = client.post(
        f"/api/v1/deliverables/{deliverable.json()['id']}/review",
        headers=headers,
        json={"status": "APPROVED", "comment": "Aceptado"},
    )
    assert reviewed.json()["status"] == "APPROVED"
    sla = client.post(
        "/api/v1/slas",
        headers=headers,
        json={"name": "Critical", "response_minutes": 15, "resolution_minutes": 120},
    )
    assert sla.status_code == 201
    assert (
        client.post(
            f"/api/v1/work-items/{work_item_id}/sla",
            headers=headers,
            json={"sla_id": sla.json()["id"]},
        ).status_code
        == 204
    )
    assert client.post("/api/v1/jobs/sla-monitor", headers=headers).json() == {"escalated": 0}
    automation = client.post(
        "/api/v1/automations",
        headers=headers,
        json={
            "name": "Avisar críticos",
            "trigger_event": "WorkItemCreated",
            "conditions": {"priority": "CRITICAL"},
            "actions": [{"type": "notify", "recipient": "manager"}],
        },
    )
    assert automation.status_code == 201
    dry_run = client.post(
        f"/api/v1/automations/{automation.json()['id']}/dry-run",
        headers=headers,
        params={"entity_id": work_item_id},
    )
    assert dry_run.json()["status"] == "DRY_RUN"
    execution_payload = {"entity_id": work_item_id, "event_key": "event-work-created-001"}
    execution = client.post(
        f"/api/v1/automations/{automation.json()['id']}/execute",
        headers=headers,
        json=execution_payload,
    )
    assert execution.status_code == 200
    assert execution.json()["result"]["matched"] is True
    repeated = client.post(
        f"/api/v1/automations/{automation.json()['id']}/execute",
        headers=headers,
        json=execution_payload,
    )
    assert repeated.json()["id"] == execution.json()["id"]
    telegram = client.post(
        "/api/v1/integrations",
        headers=headers,
        json={"name": "Telegram Bot", "provider": "telegram", "direction": "BIDIRECTIONAL"},
    )
    assert telegram.status_code == 201
    assert (
        client.post(
            f"/api/v1/integrations/{telegram.json()['id']}/identity-links",
            headers=headers,
            json={"external_user_id": "7788", "user_id": member.json()["user_id"]},
        ).status_code
        == 201
    )
    inbound_payload = {
        "update_id": 991,
        "message": {"from": {"id": 7788}, "text": "Necesito apoyo legal"},
    }
    body = json.dumps(inbound_payload, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    signature = hmac.new(
        b"development-webhook-secret", timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    webhook_headers = {
        "X-Webhook-Timestamp": timestamp,
        "X-Webhook-Signature": f"sha256={signature}",
        "Content-Type": "application/json",
    }
    inbound = client.post(
        f"/api/v1/inbound/telegram/{telegram.json()['id']}",
        headers=webhook_headers,
        content=body,
    )
    assert inbound.status_code == 202
    assert inbound.json()["status"] == "WORK_ITEM_CREATED"
    duplicate = client.post(
        f"/api/v1/inbound/telegram/{telegram.json()['id']}",
        headers=webhook_headers,
        content=body,
    )
    assert duplicate.json()["duplicate"] is True
    preference = client.put(
        "/api/v1/notification-preferences/telegram",
        headers=reviewer_headers,
        json={"channel": "telegram", "enabled": True, "quiet_hours": {"from": "22:00"}},
    )
    assert preference.status_code == 200
    outbound = client.post(
        "/api/v1/outbound",
        headers=headers,
        json={
            "integration_id": telegram.json()["id"],
            "channel": "telegram",
            "recipient": "7788",
            "body": "Recibido",
            "idempotency_key": "reply-telegram-991",
        },
    )
    assert outbound.status_code == 202
    mock_integration = client.post(
        "/api/v1/integrations",
        headers=headers,
        json={"name": "Local delivery", "provider": "mock", "direction": "OUTBOUND"},
    )
    mock_message = client.post(
        "/api/v1/outbound",
        headers=headers,
        json={
            "integration_id": mock_integration.json()["id"],
            "channel": "email",
            "recipient": "person@example.com",
            "subject": "Prueba",
            "body": "Mensaje local",
            "idempotency_key": "local-delivery-001",
        },
    )
    assert mock_message.status_code == 202
    delivery = client.post("/api/v1/jobs/outbound-delivery", headers=headers)
    assert delivery.json() == {"sent": 1, "retried": 1, "dead_letter": 0}
    agent = client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "name": "Conciencia Operativa",
            "description": "Consultas organizacionales de solo lectura",
            "capabilities": ["organizational_query", "classification"],
            "permissions": ["workitem.view"],
        },
    )
    assert agent.status_code == 201
    answer = client.post(
        "/api/v1/ask-conciencia", headers=headers, json={"question": "Resumen por estado"}
    )
    assert answer.status_code == 200
    assert answer.json()["intent"] == "status_summary"
    classification = client.post(
        "/api/v1/conciencia/classify",
        headers=headers,
        json={"title": "Revisar contrato de proveedor", "description": "Validar cláusulas"},
    )
    assert classification.json()["suggested_type"] == "LEGAL_REQUEST"
    assert classification.json()["requires_human_confirmation"] is True
    search = client.get("/api/v1/search", headers=headers, params={"query": "apoyo legal"})
    assert len(search.json()) == 1
    proposal = client.post(
        "/api/v1/agent-proposals",
        headers=headers,
        json={
            "agent_run_id": answer.json()["run_id"],
            "action_type": "set_priority",
            "target_id": inbound.json()["work_item_id"],
            "arguments": {"priority": "HIGH"},
            "risk_level": "LOW",
            "rationale": "La solicitud requiere atención pronta",
        },
    )
    assert proposal.status_code == 201
    assert (
        client.post(
            f"/api/v1/agent-proposals/{proposal.json()['id']}/execute", headers=headers
        ).status_code
        == 409
    )
    decision = client.post(
        f"/api/v1/agent-proposals/{proposal.json()['id']}/decision",
        headers=headers,
        json={"decision": "APPROVED", "comment": "Autorizado"},
    )
    assert decision.json()["status"] == "APPROVED"
    executed = client.post(
        f"/api/v1/agent-proposals/{proposal.json()['id']}/execute", headers=headers
    )
    assert executed.json()["status"] == "EXECUTED"
    intelligence = client.post("/api/v1/jobs/process-intelligence", headers=headers)
    assert "evidence" in intelligence.json()
    timeline = client.get(f"/api/v1/work-items/{work_item_id}/timeline", headers=reviewer_headers)
    assert {event["event_type"] for event in timeline.json()} >= {
        "WorkItemAssigned",
        "WorkItemStatusChanged",
        "CommentCreated",
        "ChecklistCreated",
    }
    assert len(client.get("/api/v1/work-items", headers=headers).json()) == 2
    audit = client.get("/api/v1/audit", headers=headers)
    assert audit.status_code == 200
    assert {event["action"] for event in audit.json()} >= {
        "organization.bootstrap",
        "department.create",
        "team.create",
        "role.create",
        "member.create",
        "workitem.create",
    }


def test_protected_endpoint_rejects_anonymous_user(client: TestClient) -> None:
    assert client.get("/api/v1/work-items").status_code == 401


def test_pwa_assets_are_served(client: TestClient) -> None:
    page = client.get("/app/")
    assert page.status_code == 200
    assert "LINTEAM" in page.text
    manifest = client.get("/app/manifest.webmanifest")
    assert manifest.status_code == 200
    assert manifest.json()["display"] == "standalone"
    assert "linteam-v1" in client.get("/app/sw.js").text
