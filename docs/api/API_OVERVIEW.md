# LINTEAM API Overview

Base path: `/api/v1`

The API is organization-scoped. Every authenticated request is resolved against a single organization and must not cross that boundary.

Main resources:

- `/me`
- `/organizations`
- `/departments`
- `/teams`
- `/members`
- `/work-items`
- `/work-items/{id}`
- `/work-items/{id}/comments`
- `/work-items/{id}/attachments`
- `/work-items/{id}/transition`
- `/workflows`
- `/approvals`
- `/notifications`
- `/search`
- `/analytics`
- `/service-accounts`
- `/api-keys`
- `/webhooks`

Mutation endpoints accept `Idempotency-Key` when supported.
All responses include `X-Request-ID`.
