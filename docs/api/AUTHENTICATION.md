# Authentication

LINTEAM supports two authentication paths:

- Human users via `Authorization: Bearer <access_token>`
- Service accounts via `X-API-Key: lt_live_...`

The API key is hashed at rest and is only shown once at creation time.

Example placeholder:

```http
X-API-Key: lt_live_example_placeholder
```

Every request is scoped to one organization. A service account from one organization cannot read or mutate another organization.
