from dataclasses import dataclass
from uuid import UUID

from app.domain.errors import AuthorizationError


@dataclass(frozen=True, slots=True)
class ActorContext:
    user_id: UUID
    organization_id: UUID
    permissions: frozenset[str]

    def require(self, permission: str) -> None:
        if permission not in self.permissions and "*" not in self.permissions:
            raise AuthorizationError(f"Missing permission: {permission}")
