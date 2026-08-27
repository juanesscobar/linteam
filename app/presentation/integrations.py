import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.auth import ActorContext
from app.application.use_cases import CreateWorkItem
from app.infrastructure.database import (
    ExternalEntityReferenceRecord,
    IdentityLinkRecord,
    InboundMessageRecord,
    IntegrationRecord,
    MembershipRecord,
    NotificationPreferenceRecord,
    OutboundMessageRecord,
    WebhookReceiptRecord,
    get_session,
)
from app.infrastructure.delivery import DeliveryMessage, MockDeliveryAdapter, ProviderNotConfigured
from app.infrastructure.messaging import InvalidProviderPayload, normalize_message
from app.infrastructure.sql_repositories import (
    SqlOrganizationRepository,
    SqlWorkItemRepository,
    record_audit,
)
from app.presentation.auth import current_actor
from app.settings import Settings, get_settings


class IntegrationInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    provider: Literal["whatsapp", "telegram", "email", "cafeteria", "credit", "mock"]
    direction: Literal["INBOUND", "OUTBOUND", "BIDIRECTIONAL", "READ_ONLY"]
    config: dict[str, object] = Field(default_factory=dict)
    secret_ref: str = Field(default="LINTEAM_WEBHOOK_SECRET", max_length=160)


class IdentityLinkInput(BaseModel):
    external_user_id: str = Field(min_length=1, max_length=200)
    user_id: UUID


class PreferenceInput(BaseModel):
    channel: Literal["in_app", "email", "whatsapp", "telegram", "push"]
    enabled: bool = True
    quiet_hours: dict[str, object] = Field(default_factory=dict)


class OutboundInput(BaseModel):
    integration_id: UUID | None = None
    channel: Literal["email", "whatsapp", "telegram", "push"]
    recipient: str = Field(min_length=1, max_length=320)
    subject: str = Field(default="", max_length=200)
    body: str = Field(min_length=1, max_length=20_000)
    idempotency_key: str = Field(min_length=8, max_length=160)


class ExternalReferenceInput(BaseModel):
    integration_id: UUID
    entity_type: str = Field(min_length=1, max_length=80)
    entity_id: UUID
    external_id: str = Field(min_length=1, max_length=200)
    external_url: str = Field(default="", max_length=1000)
    snapshot: dict[str, object] = Field(default_factory=dict)


router = APIRouter(prefix="/api/v1")


@router.post("/integrations", status_code=201)
def create_integration(
    payload: IntegrationInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("integration.manage")
    forbidden = {"secret", "token", "password", "api_key"} & {key.lower() for key in payload.config}
    if forbidden:
        raise HTTPException(422, "Secrets must be referenced through environment configuration")
    value = IntegrationRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        active=True,
        created_at=datetime.now(UTC),
        **payload.model_dump(),
    )
    session.add(value)
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="integration.create",
        entity_type="integration",
        entity_id=value.id,
        new_state={"provider": value.provider, "direction": value.direction},
    )
    session.commit()
    return {"id": value.id, "name": value.name, "provider": value.provider, "active": value.active}


@router.post("/integrations/{integration_id}/identity-links", status_code=201)
def link_identity(
    integration_id: UUID,
    payload: IdentityLinkInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("integration.manage")
    integration = session.scalar(
        select(IntegrationRecord).where(
            IntegrationRecord.id == integration_id,
            IntegrationRecord.organization_id == actor.organization_id,
        )
    )
    membership = session.scalar(
        select(MembershipRecord).where(
            MembershipRecord.user_id == payload.user_id,
            MembershipRecord.organization_id == actor.organization_id,
        )
    )
    if integration is None or membership is None:
        raise HTTPException(404, "Integration or member not found")
    value = IdentityLinkRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        integration_id=integration.id,
        external_user_id=payload.external_user_id,
        user_id=payload.user_id,
        verified_at=datetime.now(UTC),
    )
    session.add(value)
    session.commit()
    return {"id": value.id, "verified": True}


def verify_webhook(body: bytes, timestamp: str, signature: str, settings: Settings) -> None:
    try:
        sent_at = int(timestamp)
    except ValueError as exc:
        raise HTTPException(401, "Invalid webhook timestamp") from exc
    if abs(int(time.time()) - sent_at) > settings.webhook_tolerance_seconds:
        raise HTTPException(401, "Expired webhook")
    expected = hmac.new(
        settings.webhook_secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    received = signature.removeprefix("sha256=")
    if not hmac.compare_digest(expected, received):
        raise HTTPException(401, "Invalid webhook signature")


@router.post("/inbound/{channel}/{integration_id}", status_code=202)
async def inbound(
    channel: str,
    integration_id: UUID,
    request: Request,
    x_webhook_timestamp: Annotated[str, Header()],
    x_webhook_signature: Annotated[str, Header()],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    body = await request.body()
    verify_webhook(body, x_webhook_timestamp, x_webhook_signature, settings)
    integration = session.scalar(
        select(IntegrationRecord).where(
            IntegrationRecord.id == integration_id,
            IntegrationRecord.provider == channel,
            IntegrationRecord.active.is_(True),
        )
    )
    if integration is None:
        raise HTTPException(404, "Integration not found")
    try:
        payload = json.loads(body)
        message = normalize_message(channel, payload)
    except (json.JSONDecodeError, InvalidProviderPayload) as exc:
        raise HTTPException(422, str(exc)) from exc
    receipt = session.scalar(
        select(WebhookReceiptRecord).where(
            WebhookReceiptRecord.integration_id == integration.id,
            WebhookReceiptRecord.external_event_id == message.event_id,
        )
    )
    if receipt:
        return {"receipt_id": receipt.id, "status": receipt.status, "duplicate": True}
    now = datetime.now(UTC)
    receipt = WebhookReceiptRecord(
        id=uuid4(),
        organization_id=integration.organization_id,
        integration_id=integration.id,
        external_event_id=message.event_id,
        payload_hash=hashlib.sha256(body).hexdigest(),
        status="RECEIVED",
        received_at=now,
        processed_at=None,
    )
    link = session.scalar(
        select(IdentityLinkRecord).where(
            IdentityLinkRecord.integration_id == integration.id,
            IdentityLinkRecord.external_user_id == message.external_user_id,
        )
    )
    work_item_id = None
    inbound_status = "IDENTITY_REQUIRED"
    if link and message.text.strip():
        membership = session.scalar(
            select(MembershipRecord).where(
                MembershipRecord.organization_id == integration.organization_id,
                MembershipRecord.user_id == link.user_id,
            )
        )
        if membership:
            from app.application.auth import ActorContext

            item = CreateWorkItem(
                SqlOrganizationRepository(session), SqlWorkItemRepository(session)
            ).execute(
                ActorContext(
                    link.user_id,
                    integration.organization_id,
                    frozenset(membership.permissions)
                    | frozenset(
                        {
                            permission.code
                            for role in membership.roles
                            for permission in role.permissions
                        }
                    ),
                ),
                title=message.text[:200],
                description=message.text,
                type_code="REQUEST",
            )
            work_item_id, inbound_status = item.id, "WORK_ITEM_CREATED"
    inbound_message = InboundMessageRecord(
        id=uuid4(),
        organization_id=integration.organization_id,
        integration_id=integration.id,
        channel=channel,
        external_event_id=message.event_id,
        external_user_id=message.external_user_id,
        text=message.text,
        normalized={"channel": channel, "event_id": message.event_id},
        status=inbound_status,
        work_item_id=work_item_id,
        received_at=now,
    )
    receipt.status, receipt.processed_at = inbound_status, now
    session.add_all([receipt, inbound_message])
    session.commit()
    return {
        "receipt_id": receipt.id,
        "status": inbound_status,
        "work_item_id": work_item_id,
        "duplicate": False,
    }


@router.put("/notification-preferences/{channel}")
def set_preference(
    channel: str,
    payload: PreferenceInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    if channel != payload.channel:
        raise HTTPException(422, "Channel mismatch")
    value = session.scalar(
        select(NotificationPreferenceRecord).where(
            NotificationPreferenceRecord.organization_id == actor.organization_id,
            NotificationPreferenceRecord.user_id == actor.user_id,
            NotificationPreferenceRecord.channel == channel,
        )
    )
    if value is None:
        value = NotificationPreferenceRecord(
            id=uuid4(),
            organization_id=actor.organization_id,
            user_id=actor.user_id,
            channel=channel,
            enabled=payload.enabled,
            quiet_hours=payload.quiet_hours,
        )
        session.add(value)
    else:
        value.enabled, value.quiet_hours = payload.enabled, payload.quiet_hours
    session.commit()
    return {"channel": channel, "enabled": value.enabled, "quiet_hours": value.quiet_hours}


@router.post("/outbound", status_code=202)
def enqueue_outbound(
    payload: OutboundInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("notification.send")
    previous = session.scalar(
        select(OutboundMessageRecord).where(
            OutboundMessageRecord.idempotency_key == payload.idempotency_key,
            OutboundMessageRecord.organization_id == actor.organization_id,
        )
    )
    if previous:
        return {"id": previous.id, "status": previous.status, "duplicate": True}
    if payload.integration_id and not session.scalar(
        select(IntegrationRecord.id).where(
            IntegrationRecord.id == payload.integration_id,
            IntegrationRecord.organization_id == actor.organization_id,
        )
    ):
        raise HTTPException(404, "Integration not found")
    value = OutboundMessageRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        status="PENDING",
        attempts=0,
        next_attempt_at=datetime.now(UTC),
        last_error="",
        created_at=datetime.now(UTC),
        **payload.model_dump(),
    )
    session.add(value)
    session.commit()
    return {"id": value.id, "status": value.status, "duplicate": False}


@router.post("/external-references", status_code=201)
def add_external_reference(
    payload: ExternalReferenceInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    actor.require("integration.manage")
    integration = session.scalar(
        select(IntegrationRecord).where(
            IntegrationRecord.id == payload.integration_id,
            IntegrationRecord.organization_id == actor.organization_id,
            IntegrationRecord.direction == "READ_ONLY",
        )
    )
    if integration is None:
        raise HTTPException(404, "Read-only integration not found")
    value = ExternalEntityReferenceRecord(
        id=uuid4(),
        organization_id=actor.organization_id,
        synced_at=datetime.now(UTC),
        **payload.model_dump(),
    )
    session.add(value)
    session.commit()
    return {"id": value.id, "synced_at": value.synced_at, "snapshot": value.snapshot}


@router.post("/jobs/outbound-delivery")
def deliver_outbound(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
    limit: int = 50,
) -> dict[str, int]:
    actor.require("system.jobs")
    now = datetime.now(UTC)
    messages = session.scalars(
        select(OutboundMessageRecord)
        .where(
            OutboundMessageRecord.organization_id == actor.organization_id,
            OutboundMessageRecord.status.in_(["PENDING", "RETRY"]),
            OutboundMessageRecord.next_attempt_at <= now,
        )
        .order_by(OutboundMessageRecord.created_at)
        .limit(min(max(limit, 1), 200))
    ).all()
    sent = retried = dead = 0
    for message in messages:
        integration = (
            session.get(IntegrationRecord, message.integration_id)
            if message.integration_id
            else None
        )
        try:
            if integration is None or integration.organization_id != actor.organization_id:
                raise ProviderNotConfigured("Integration is unavailable")
            if integration.provider != "mock":
                raise ProviderNotConfigured(
                    f"Provider {integration.provider} has no delivery credentials"
                )
            external_id = MockDeliveryAdapter().send(
                DeliveryMessage(message.channel, message.recipient, message.subject, message.body)
            )
            message.status, message.last_error = "SENT", ""
            message.attempts += 1
            sent += 1
            record_audit(
                session,
                organization_id=actor.organization_id,
                actor_id=actor.user_id,
                action="outbound.sent",
                entity_type="outbound_message",
                entity_id=message.id,
                new_state={"external_id": external_id},
            )
        except (ProviderNotConfigured, ValueError) as exc:
            message.attempts += 1
            message.last_error = str(exc)[:500]
            if message.attempts >= 5:
                message.status = "DEAD_LETTER"
                dead += 1
            else:
                message.status = "RETRY"
                message.next_attempt_at = now + timedelta(minutes=2**message.attempts)
                retried += 1
    session.commit()
    return {"sent": sent, "retried": retried, "dead_letter": dead}
