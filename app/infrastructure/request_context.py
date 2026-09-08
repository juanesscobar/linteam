from contextvars import ContextVar
from typing import Any

request_id_context: ContextVar[str | None] = ContextVar("linteam_request_id", default=None)
principal_type_context: ContextVar[str | None] = ContextVar("linteam_principal_type", default=None)
service_account_id_context: ContextVar[str | None] = ContextVar("linteam_service_account_id", default=None)
api_key_id_context: ContextVar[str | None] = ContextVar("linteam_api_key_id", default=None)


def set_request_context(*, request_id: str | None = None, principal_type: str | None = None) -> list[Any]:
    tokens: list[Any] = []
    if request_id is not None:
        tokens.append(request_id_context.set(request_id))
    if principal_type is not None:
        tokens.append(principal_type_context.set(principal_type))
    return tokens


def set_principal_context(
    *, principal_type: str, service_account_id: str | None = None, api_key_id: str | None = None
) -> list[Any]:
    tokens: list[Any] = [principal_type_context.set(principal_type)]
    if service_account_id is not None:
        tokens.append(service_account_id_context.set(service_account_id))
    if api_key_id is not None:
        tokens.append(api_key_id_context.set(api_key_id))
    return tokens


def context_value(value: ContextVar[str | None]) -> str | None:
    return value.get()
