import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.auth import ActorContext
from app.application.linteam_agent import AgentRequest, LinteamAgentService
from app.infrastructure.database import (
    CommunicationIdentityRecord,
    CommunicationLinkTokenRecord,
    MembershipRecord,
    ProcessedChannelEventRecord,
    get_session,
)
from app.infrastructure.sql_repositories import record_audit
from app.infrastructure.telegram import TelegramBotClient
from app.presentation.auth import current_actor
from app.settings import Settings, get_settings

logger = logging.getLogger("linteam.telegram")
router = APIRouter(prefix="/api/v1")


class AgentExecuteInput(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


def response_body(value: object) -> dict[str, object]:
    return {
        "text": value.text,
        "status": value.status,
        "action": value.action,
        "entity_id": value.entity_id,
        "confirmation_id": value.confirmation_id,
    }


@router.get("/me/communication-channels")
def communication_channels(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> list[dict[str, object]]:
    rows = session.scalars(
        select(CommunicationIdentityRecord).where(
            CommunicationIdentityRecord.organization_id == actor.organization_id,
            CommunicationIdentityRecord.user_id == actor.user_id,
        )
    ).all()
    return [
        {
            "channel": row.channel,
            "connected": True,
            "enabled": row.enabled,
            "display_name": row.display_name,
        }
        for row in rows
    ]


@router.post("/me/communication-channels/telegram/link")
def telegram_link(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    if not settings.telegram_bot_username:
        raise HTTPException(503, "Telegram bot username is not configured")
    raw, now = secrets.token_urlsafe(32), datetime.now(UTC)
    session.add(
        CommunicationLinkTokenRecord(
            id=uuid4(),
            organization_id=actor.organization_id,
            user_id=actor.user_id,
            channel="TELEGRAM",
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=now + timedelta(minutes=10),
            used_at=None,
            created_at=now,
        )
    )
    record_audit(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="telegram.link.request",
        entity_type="communication_identity",
        entity_id=actor.user_id,
        new_state={"channel": "TELEGRAM"},
    )
    session.commit()
    return {
        "url": f"https://t.me/{settings.telegram_bot_username}?start={raw}",
        "expires_at": now + timedelta(minutes=10),
    }


@router.delete("/me/communication-channels/telegram", status_code=204)
def telegram_unlink(
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    row = session.scalar(
        select(CommunicationIdentityRecord).where(
            CommunicationIdentityRecord.organization_id == actor.organization_id,
            CommunicationIdentityRecord.user_id == actor.user_id,
            CommunicationIdentityRecord.channel == "TELEGRAM",
        )
    )
    if row:
        row.enabled, row.updated_at = False, datetime.now(UTC)
        record_audit(
            session,
            organization_id=actor.organization_id,
            actor_id=actor.user_id,
            action="telegram.unlink",
            entity_type="communication_identity",
            entity_id=row.id,
            new_state={"channel": "TELEGRAM"},
        )
        session.commit()


@router.post("/agent/execute")
def agent_execute(
    payload: AgentExecuteInput,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    return response_body(
        LinteamAgentService(session).execute(AgentRequest(actor, "WEB", payload.text, str(uuid4())))
    )


@router.post("/agent/confirm/{confirmation_id}")
def agent_confirm(
    confirmation_id: str,
    actor: Annotated[ActorContext, Depends(current_actor)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    return response_body(LinteamAgentService(session).confirm(actor, "WEB", confirmation_id))


@router.post("/integrations/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
    session: Annotated[Session, Depends(get_session)] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
) -> dict[str, object]:
    if not settings.telegram_enabled or not settings.telegram_webhook_secret:
        raise HTTPException(404, "Telegram is disabled")
    if not x_telegram_bot_api_secret_token or not hmac.compare_digest(
        x_telegram_bot_api_secret_token, settings.telegram_webhook_secret
    ):
        logger.warning("telegram_webhook_rejected")
        raise HTTPException(401, "Invalid Telegram webhook secret")
    payload = await request.json()
    update_id = str(payload.get("update_id", ""))
    message = payload.get("message") or payload.get("callback_query")
    if not update_id or not isinstance(message, dict) or not isinstance(message.get("from"), dict):
        raise HTTPException(422, "Invalid Telegram update")
    if session.scalar(
        select(ProcessedChannelEventRecord).where(
            ProcessedChannelEventRecord.channel == "TELEGRAM",
            ProcessedChannelEventRecord.external_event_id == update_id,
        )
    ):
        return {"status": "DUPLICATE"}
    sender, external_id = message["from"], str(message["from"]["id"])
    text = str(message.get("text") or message.get("data") or "")
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    chat_id = str(chat.get("id", external_id))
    organization_id = None
    if text.startswith("/start "):
        token = session.scalar(
            select(CommunicationLinkTokenRecord).where(
                CommunicationLinkTokenRecord.channel == "TELEGRAM",
                CommunicationLinkTokenRecord.token_hash
                == hashlib.sha256(text.split(maxsplit=1)[1].encode()).hexdigest(),
            )
        )
        if token is None or token.used_at or token.expires_at <= datetime.now(UTC):
            status, reply = "LINK_INVALID", "El enlace no es válido o expiró."
        else:
            identity = session.scalar(
                select(CommunicationIdentityRecord).where(
                    CommunicationIdentityRecord.channel == "TELEGRAM",
                    CommunicationIdentityRecord.external_user_id == external_id,
                )
            )
            organization_id = token.organization_id
            if identity and identity.user_id != token.user_id:
                status, reply = "LINK_CONFLICT", "Esta cuenta de Telegram ya está vinculada."
            else:
                now = datetime.now(UTC)
                if identity is None:
                    session.add(
                        CommunicationIdentityRecord(
                            id=uuid4(),
                            organization_id=token.organization_id,
                            user_id=token.user_id,
                            channel="TELEGRAM",
                            external_user_id=external_id,
                            external_chat_id=chat_id,
                            display_name=str(sender.get("username", "")),
                            verified_at=now,
                            enabled=True,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                else:
                    identity.enabled, identity.external_chat_id, identity.updated_at = (
                        True,
                        chat_id,
                        now,
                    )
                token.used_at, status, reply = (
                    now,
                    "LINKED",
                    "Tu cuenta de Telegram quedó vinculada a LINTEAM.",
                )
    else:
        identity = session.scalar(
            select(CommunicationIdentityRecord).where(
                CommunicationIdentityRecord.channel == "TELEGRAM",
                CommunicationIdentityRecord.external_user_id == external_id,
                CommunicationIdentityRecord.enabled.is_(True),
            )
        )
        if identity is None:
            status, reply = (
                "IDENTITY_REQUIRED",
                "Conectá tu cuenta desde LINTEAM antes de usar el agente.",
            )
        else:
            organization_id = identity.organization_id
            membership = session.scalar(
                select(MembershipRecord).where(
                    MembershipRecord.organization_id == identity.organization_id,
                    MembershipRecord.user_id == identity.user_id,
                )
            )
            if membership is None:
                status, reply = "IDENTITY_REQUIRED", "Tu cuenta no tiene acceso activo a LINTEAM."
            else:
                permissions = frozenset(membership.permissions) | frozenset(
                    p.code for role in membership.roles for p in role.permissions
                )
                actor, service = (
                    ActorContext(identity.user_id, identity.organization_id, permissions),
                    LinteamAgentService(session),
                )
                result = (
                    service.confirm(actor, "TELEGRAM", text[8:])
                    if text.startswith("confirm:")
                    else service.execute(AgentRequest(actor, "TELEGRAM", text, update_id))
                )
                status, reply = result.status, result.text
    session.add(
        ProcessedChannelEventRecord(
            id=uuid4(),
            channel="TELEGRAM",
            external_event_id=update_id,
            organization_id=organization_id,
            status=status,
            created_at=datetime.now(UTC),
        )
    )
    session.commit()
    logger.info("telegram.update.processed update_id=%s status=%s", update_id, status)
    try:
        client = TelegramBotClient(settings)
        await client.send_message(chat_id, reply)
    except RuntimeError:
        # The inbound command was already committed; a Telegram outage cannot retry a mutation.
        logger.warning("telegram.delivery.failed update_id=%s", update_id)
        return {"status": status, "delivery": "FAILED"}
    logger.info("telegram.delivery.sent update_id=%s", update_id)
    return {"status": status, "delivery": "SENT"}
