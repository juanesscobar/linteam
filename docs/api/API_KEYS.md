# API Keys

API keys are created under a service account and carry explicit scopes.

Stored fields:

- prefix
- secure hash
- scopes
- created_at
- expires_at
- revoked_at
- last_used_at

Creation response returns the full key once. After that only the prefix is visible.

Recommended scopes:

- `workitems:read`
- `workitems:create`
- `workitems:update`
- `workitems:assign`
- `workitems:transition`
- `workitems:comment`
- `departments:read`
- `members:read`
- `analytics:read`
- `webhooks:manage`
