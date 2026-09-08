from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database import IdempotencyRecord


@dataclass(slots=True)
class IdempotencyResult:
    replay: bool
    conflict: bool
    status_code: int | None = None
    body: dict[str, object] | None = None


def hash_request(body: dict[str, object]) -> str:
    normalized = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(normalized).hexdigest()


def reserve(
    session: Session,
    *,
    organization_id: object,
    namespace: str,
    idempotency_key: str,
    request_hash: str,
) -> IdempotencyResult:
    record = session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.organization_id == organization_id,
            IdempotencyRecord.namespace == namespace,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
    )
    if record is None:
        session.add(
            IdempotencyRecord(
                id=uuid4(),
                organization_id=organization_id,
                namespace=namespace,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                response_status=0,
                response_body=None,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        return IdempotencyResult(replay=False, conflict=False)
    if record.request_hash != request_hash:
        return IdempotencyResult(replay=False, conflict=True)
    if record.response_status == 0:
        return IdempotencyResult(replay=False, conflict=True)
    if record.response_status:
        return IdempotencyResult(
            replay=True,
            conflict=False,
            status_code=record.response_status,
            body=record.response_body,
        )
    return IdempotencyResult(replay=False, conflict=False)


def store_response(
    session: Session,
    *,
    organization_id: object,
    namespace: str,
    idempotency_key: str,
    request_hash: str,
    status_code: int,
    body: dict[str, object] | None,
) -> None:
    record = session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.organization_id == organization_id,
            IdempotencyRecord.namespace == namespace,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
    )
    if record is None:
        session.add(
            IdempotencyRecord(
                id=uuid4(),
                organization_id=organization_id,
                namespace=namespace,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                response_status=status_code,
                response_body=body,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        return
    record.request_hash = request_hash
    record.response_status = status_code
    record.response_body = body
    record.updated_at = datetime.now(UTC)
