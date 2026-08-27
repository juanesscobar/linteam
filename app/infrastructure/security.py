from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash

from app.settings import Settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    return password_hash.verify(password, encoded)


def create_token(
    user_id: UUID,
    organization_id: UUID,
    settings: Settings,
    token_type: str,
) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "org": str(organization_id),
        "iat": now,
        "exp": now
        + (
            timedelta(minutes=settings.access_token_minutes)
            if token_type == "access"
            else timedelta(days=settings.refresh_token_days)
        ),
        "type": token_type,
        "jti": str(uuid4()),
    }
    return jwt.encode(claims, settings.secret_key, algorithm="HS256")


def decode_token(token: str, settings: Settings, expected_type: str) -> tuple[UUID, UUID, UUID]:
    claims = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    if claims.get("type") != expected_type:
        raise jwt.InvalidTokenError("Invalid token type")
    return UUID(claims["sub"]), UUID(claims["org"]), UUID(claims["jti"])


def create_access_token(user_id: UUID, organization_id: UUID, settings: Settings) -> str:
    return create_token(user_id, organization_id, settings, "access")


def create_refresh_token(user_id: UUID, organization_id: UUID, settings: Settings) -> str:
    return create_token(user_id, organization_id, settings, "refresh")


def decode_access_token(token: str, settings: Settings) -> tuple[UUID, UUID]:
    user_id, organization_id, _ = decode_token(token, settings, "access")
    return user_id, organization_id
