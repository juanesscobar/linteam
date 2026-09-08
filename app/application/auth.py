from dataclasses import dataclass
from uuid import UUID

from app.domain.errors import AuthorizationError


@dataclass(frozen=True, slots=True)
class ActorContext:
    user_id: UUID
    organization_id: UUID
    permissions: frozenset[str]
    principal_type: str = "HUMAN_USER"
    service_account_id: UUID | None = None
    api_key_id: UUID | None = None
    request_id: str | None = None

    def require(self, permission: str) -> None:
        if permission not in self.permissions and "*" not in self.permissions:
            raise AuthorizationError(f"Missing permission: {permission}")

    def has(self, permission: str) -> bool:
        return permission in self.permissions or "*" in self.permissions

    def require_any(self, *permissions: str) -> None:
        if not any(self.has(permission) for permission in permissions):
            raise AuthorizationError(f"Missing one of: {', '.join(permissions)}")
