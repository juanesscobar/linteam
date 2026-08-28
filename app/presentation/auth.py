import hashlib
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.auth import ActorContext
from app.infrastructure.database import (
    MembershipRecord,
    RefreshSessionRecord,
    UserRecord,
    get_session,
)
from app.infrastructure.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_token,
    verify_password,
)
from app.settings import Settings, get_settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    organization_id: UUID | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


def current_actor(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ActorContext:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id, organization_id = decode_access_token(token, settings)
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise unauthorized from exc
    membership = session.scalar(
        select(MembershipRecord).where(
            MembershipRecord.user_id == user_id,
            MembershipRecord.organization_id == organization_id,
        )
    )
    user = session.get(UserRecord, user_id)
    if membership is None or user is None or not user.is_active:
        raise unauthorized
    role_permissions = {
        permission.code for role in membership.roles for permission in role.permissions
    }
    return ActorContext(
        user_id,
        organization_id,
        frozenset(membership.permissions) | frozenset(role_permissions),
    )


def authenticate(payload: LoginRequest, session: Session, settings: Settings) -> TokenResponse:
    user = session.scalar(select(UserRecord).where(UserRecord.email == payload.email.lower()))
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    memberships = list(
        session.scalars(select(MembershipRecord).where(MembershipRecord.user_id == user.id)).all()
    )
    membership = (
        next((m for m in memberships if m.organization_id == payload.organization_id), None)
        if payload.organization_id
        else (memberships[0] if len(memberships) == 1 else None)
    )
    if membership is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    response, _ = issue_token_pair(user.id, membership.organization_id, session, settings)
    session.commit()
    return response


def issue_token_pair(
    user_id: UUID, organization_id: UUID, session: Session, settings: Settings
) -> tuple[TokenResponse, RefreshSessionRecord]:
    access_token = create_access_token(user_id, organization_id, settings)
    refresh_token = create_refresh_token(user_id, organization_id, settings)
    _, _, session_id = decode_token(refresh_token, settings, "refresh")
    record = RefreshSessionRecord(
        id=session_id,
        user_id=user_id,
        organization_id=organization_id,
        token_hash=hashlib.sha256(refresh_token.encode()).hexdigest(),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
        revoked_at=None,
        replaced_by=None,
        created_at=datetime.now(UTC),
    )
    session.add(record)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token), record


def rotate_refresh_token(
    payload: RefreshRequest, session: Session, settings: Settings
) -> TokenResponse:
    unauthorized = HTTPException(status_code=401, detail="Invalid refresh token")
    try:
        user_id, organization_id, session_id = decode_token(
            payload.refresh_token, settings, "refresh"
        )
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise unauthorized from exc
    record = session.get(RefreshSessionRecord, session_id)
    if (
        record is None
        or record.token_hash != hashlib.sha256(payload.refresh_token.encode()).hexdigest()
        or record.revoked_at is not None
        or record.expires_at.replace(tzinfo=UTC) <= datetime.now(UTC)
    ):
        raise unauthorized
    membership = session.scalar(
        select(MembershipRecord).where(
            MembershipRecord.user_id == user_id, MembershipRecord.organization_id == organization_id
        )
    )
    user = session.get(UserRecord, user_id)
    if membership is None or user is None or not user.is_active:
        raise unauthorized
    response, replacement = issue_token_pair(user_id, organization_id, session, settings)
    record.revoked_at, record.replaced_by = datetime.now(UTC), replacement.id
    session.commit()
    return response


def revoke_refresh_token(payload: RefreshRequest, session: Session, settings: Settings) -> None:
    try:
        _, _, session_id = decode_token(payload.refresh_token, settings, "refresh")
    except (jwt.InvalidTokenError, ValueError):
        return
    record = session.get(RefreshSessionRecord, session_id)
    if record and record.token_hash == hashlib.sha256(payload.refresh_token.encode()).hexdigest():
        record.revoked_at = datetime.now(UTC)
        session.commit()
