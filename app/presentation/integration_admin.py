from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.auth import ActorContext
from app.infrastructure.database import (
    ApiKeyRecord,
    ServiceAccountRecord,
    WebhookDeliveryRecord,
    WebhookRecord,
    get_session,
)
from app.infrastructure.sql_repositories import record_audit
from app.presentation.auth import current_actor
from app.settings import Settings, get_settings

ALLOWED_SCOPES = {
    "organization:read",
    "departments:read",
    "members:read",
    "workitems:read",
    "workitems:create",
    "workitems:update",
    "workitems:assign",
    "workitems:transition",
    "workitems:comment",
    "approvals:read",
    "approvals:request",
    "approvals:decide",
    "analytics:read",
    "webhooks:manage",
}


def normalize_scopes(scopes: list[str]) -> list[str]:
    unique = []
    for scope in scopes:
        scope = scope.strip()
        if scope not in ALLOWED_SCOPES:
            raise HTTPException(422, f"Unsupported scope: {scope}")
        if scope not in unique:
            unique.append(scope)
    return unique


class ServiceAccountInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=500)
    status: Literal["ACTIVE", "DISABLED"] = "ACTIVE"


class ServiceAccountView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    name: str
    description: str
    status: str
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class ApiKeyInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class ApiKeyView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    service_account_id: UUID
    name: str
    prefix: str
    scopes: list[str]
    expires_at: datetime | None
    revoked_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime


class ApiKeyCreateResponse(ApiKeyView):
    full_key: str


class WebhookInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    url: str = Field(min_length=8, max_length=1000)
    secret: str = Field(default_factory=lambda: secrets.token_urlsafe(32), max_length=255)
    events: list[str] = Field(default_factory=list, max_length=100)
    active: bool = True


class WebhookView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    name: str
    url: str
    events: list[str]
    active: bool
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class WebhookDeliveryView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    webhook_id: UUID
    event_id: UUID
    event_type: str
    status: str
    attempts: int
    next_attempt_at: datetime
    delivered_at: datetime | None
    last_error: str
    created_at: datetime


router = APIRouter(prefix="/api/v1", tags=["integrations"])


def _ensure_write_access(actor: ActorContext) -> None:
    actor.require_any("integration.manage", "webhooks:manage")


def _ensure_read_access(actor: ActorContext) -> None:
    actor.require_any("integration.manage", "webhooks:manage", "organization:read")


def _api_key_scopes(scopes: list[str]) -> list[str]:
    values = normalize_scopes(scopes)
    aliases = {
        "organization:read": ["organization:view"],
        "departments:read": ["department.view"],
        "members:read": ["member.view"],
        "workitems:read": ["workitem.view"],
        "workitems:create": ["workitem.create"],
        "workitems:update": ["workitem.update"],
        "workitems:assign": ["workitem.assign"],
        "workitems:transition": ["workitem.transition"],
        "workitems:comment": ["workitem.comment", "workitem.update"],
        "approvals:read": ["approval.view"],
        "approvals:request": ["workitem.approve"],
        "approvals:decide": ["workitem.approve"],
        "analytics:read": ["executive.view"],
        "webhooks:manage": ["integration.manage"],
    }
    expanded: list[str] = []
    for scope in values:
        expanded.append(scope)
        expanded.extend(aliases.get(scope, []))
    return sorted(set(expanded))


@router.get("/service-accounts", response_model=list[ServiceAccountView])
def list_service_accounts(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> list[ServiceAccountRecord]:
    _ensure_read_access(actor)
    return session.scalars(
        select(ServiceAccountRecord)
        .where(ServiceAccountRecord.organization_id == actor.organization_id)
        .order_by(ServiceAccountRecord.created_at.desc())
    ).all()


@router.post("/service-accounts", response_model=ServiceAccountView, status_code=201)
def create_service_account(
    payload: ServiceAccountInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> ServiceAccountRecord:
    _ensure_write_access(actor)
    account = ServiceAccountRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        status=payload.status,
        created_by=actor.user_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(account)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="service_account.create",
        entity_type="service_account",
        entity_id=account.id,
        new_state={"name": account.name, "status": account.status},
    )
    session.commit()
    return account


@router.post("/service-accounts/{service_account_id}/disable", status_code=204)
def disable_service_account(
    service_account_id: UUID,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    _ensure_write_access(actor)
    account = session.scalar(
        select(ServiceAccountRecord).where(
            ServiceAccountRecord.id == service_account_id,
            ServiceAccountRecord.organization_id == actor.organization_id,
        )
    )
    if account is None:
        raise HTTPException(404, "Service account not found")
    account.status = "DISABLED"
    account.updated_at = datetime.now(UTC)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="service_account.disable",
        entity_type="service_account",
        entity_id=account.id,
        new_state={"status": account.status},
    )
    session.commit()


@router.get("/api-keys", response_model=list[ApiKeyView])
def list_api_keys(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> list[ApiKeyRecord]:
    _ensure_read_access(actor)
    return session.scalars(
        select(ApiKeyRecord)
        .where(ApiKeyRecord.organization_id == actor.organization_id)
        .order_by(ApiKeyRecord.created_at.desc())
    ).all()


@router.post("/service-accounts/{service_account_id}/api-keys", response_model=ApiKeyCreateResponse, status_code=201)
def create_api_key(
    service_account_id: UUID,
    payload: ApiKeyInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> ApiKeyCreateResponse:
    _ensure_write_access(actor)
    service_account = session.scalar(
        select(ServiceAccountRecord).where(
            ServiceAccountRecord.id == service_account_id,
            ServiceAccountRecord.organization_id == actor.organization_id,
        )
    )
    if service_account is None:
        raise HTTPException(404, "Service account not found")
    full_key = f"lt_live_{secrets.token_urlsafe(32)}"
    api_key = ApiKeyRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        service_account_id=service_account.id,
        name=payload.name.strip(),
        prefix=full_key[:16],
        key_hash=hashlib.sha256(full_key.encode()).hexdigest(),
        scopes=_api_key_scopes(payload.scopes),
        expires_at=payload.expires_at,
        revoked_at=None,
        last_used_at=None,
        created_by=actor.user_id,
        created_at=datetime.now(UTC),
    )
    session.add(api_key)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="api_key.create",
        entity_type="api_key",
        entity_id=api_key.id,
        new_state={"prefix": api_key.prefix, "scopes": api_key.scopes, "service_account_id": str(service_account.id)},
    )
    session.commit()
    return ApiKeyCreateResponse(
        id=api_key.id,
        service_account_id=api_key.service_account_id,
        name=api_key.name,
        prefix=api_key.prefix,
        scopes=api_key.scopes,
        expires_at=api_key.expires_at,
        revoked_at=api_key.revoked_at,
        last_used_at=api_key.last_used_at,
        created_at=api_key.created_at,
        full_key=full_key,
    )


@router.post("/api-keys/{api_key_id}/revoke", status_code=204)
def revoke_api_key(
    api_key_id: UUID,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    _ensure_write_access(actor)
    api_key = session.scalar(
        select(ApiKeyRecord).where(
            ApiKeyRecord.id == api_key_id,
            ApiKeyRecord.organization_id == actor.organization_id,
        )
    )
    if api_key is None:
        raise HTTPException(404, "API key not found")
    api_key.revoked_at = datetime.now(UTC)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="api_key.revoke",
        entity_type="api_key",
        entity_id=api_key.id,
        new_state={"revoked": True, "prefix": api_key.prefix},
    )
    session.commit()


@router.get("/webhooks", response_model=list[WebhookView])
def list_webhooks(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> list[WebhookRecord]:
    _ensure_read_access(actor)
    return session.scalars(
        select(WebhookRecord)
        .where(WebhookRecord.organization_id == actor.organization_id)
        .order_by(WebhookRecord.created_at.desc())
    ).all()


@router.post("/webhooks", response_model=WebhookView, status_code=201)
def create_webhook(
    payload: WebhookInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> WebhookRecord:
    _ensure_write_access(actor)
    webhook = WebhookRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        name=payload.name.strip(),
        url=payload.url.strip(),
        secret=payload.secret.strip(),
        events=sorted(set(payload.events)),
        active=payload.active,
        created_by=actor.user_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(webhook)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="webhook.create",
        entity_type="webhook",
        entity_id=webhook.id,
        new_state={"name": webhook.name, "url": webhook.url, "events": webhook.events},
    )
    session.commit()
    return webhook


@router.post("/webhooks/{webhook_id}/disable", status_code=204)
def disable_webhook(
    webhook_id: UUID,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    _ensure_write_access(actor)
    webhook = session.scalar(
        select(WebhookRecord).where(
            WebhookRecord.id == webhook_id,
            WebhookRecord.organization_id == actor.organization_id,
        )
    )
    if webhook is None:
        raise HTTPException(404, "Webhook not found")
    webhook.active = False
    webhook.updated_at = datetime.now(UTC)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="webhook.disable",
        entity_type="webhook",
        entity_id=webhook.id,
        new_state={"active": False},
    )
    session.commit()


@router.get("/webhooks/{webhook_id}/deliveries", response_model=list[WebhookDeliveryView])
def list_webhook_deliveries(
    webhook_id: UUID,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> list[WebhookDeliveryRecord]:
    _ensure_read_access(actor)
    return session.scalars(
        select(WebhookDeliveryRecord)
        .where(
            WebhookDeliveryRecord.organization_id == actor.organization_id,
            WebhookDeliveryRecord.webhook_id == webhook_id,
        )
        .order_by(WebhookDeliveryRecord.created_at.desc())
    ).all()


def _dispatch_delivery(session: Session, delivery: WebhookDeliveryRecord, settings: Settings) -> None:
    webhook = session.get(WebhookRecord, delivery.webhook_id)
    if webhook is None or not webhook.active:
        raise HTTPException(404, "Webhook not found")
    timestamp = str(int(datetime.now(UTC).timestamp()))
    body = json.dumps(
        {
            "event_id": str(delivery.event_id),
            "event_type": delivery.event_type,
            "organization_id": str(delivery.organization_id),
            "payload": delivery.payload,
        },
        separators=(",", ":"),
    ).encode()
    signature = hmac.new(webhook.secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    request = urllib.request.Request(
        webhook.url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-LinTeam-Event": delivery.event_type,
            "X-LinTeam-Delivery": str(delivery.id),
            "X-LinTeam-Timestamp": timestamp,
            "X-LinTeam-Signature": signature,
        },
    )
    with urllib.request.urlopen(request, timeout=5) as response:  # nosec B310
        if response.status >= 400:
            raise urllib.error.HTTPError(webhook.url, response.status, "webhook failed", response.headers, None)


@router.post("/jobs/webhooks-deliver")
def deliver_webhooks(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = 50,
) -> dict[str, int]:
    actor.require_any("system.jobs", "webhooks:manage")
    now = datetime.now(UTC)
    deliveries = session.scalars(
        select(WebhookDeliveryRecord)
        .where(
            WebhookDeliveryRecord.organization_id == actor.organization_id,
            WebhookDeliveryRecord.status.in_(["PENDING", "RETRY"]),
            WebhookDeliveryRecord.next_attempt_at <= now,
        )
        .order_by(WebhookDeliveryRecord.created_at)
        .limit(min(max(limit, 1), 200))
    ).all()
    sent = retried = dead_letter = 0
    for delivery in deliveries:
        try:
            _dispatch_delivery(session, delivery, settings)
            delivery.status = "DELIVERED"
            delivery.delivered_at = now
            delivery.attempts += 1
            delivery.last_error = ""
            sent += 1
        except Exception as exc:  # noqa: BLE001
            delivery.attempts += 1
            delivery.last_error = str(exc)[:500]
            if delivery.attempts >= 5:
                delivery.status = "DEAD_LETTER"
                dead_letter += 1
            else:
                delivery.status = "RETRY"
                delivery.next_attempt_at = now + timedelta(minutes=2**delivery.attempts)
                retried += 1
    session.commit()
    return {"sent": sent, "retried": retried, "dead_letter": dead_letter}
