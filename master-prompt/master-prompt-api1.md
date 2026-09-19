LINTEAM — API & INTEGRATION LAYER PHASE

You are continuing development of the existing LINTEAM repository.

The next objective is to turn LINTEAM into a secure integrable platform so:

1. Conciencia can connect as an agent/orchestrator.
2. Other internal tools can connect.
3. Authorized coworkers can build integrations.
4. External systems can create/read/update allowed organizational work.
5. LINTEAM can emit events to other systems.

Do NOT redesign the core domain.
Do NOT allow direct database access from integrations.

==================================================
1. API
==================================================

Create a stable versioned API:

/api/v1

Expose or normalize:

/api/v1/me
/api/v1/organizations
/api/v1/departments
/api/v1/teams
/api/v1/members

/api/v1/work-items
/api/v1/work-items/{id}
/api/v1/work-items/{id}/comments
/api/v1/work-items/{id}/attachments
/api/v1/work-items/{id}/transition

/api/v1/workflows
/api/v1/approvals
/api/v1/notifications
/api/v1/search
/api/v1/analytics

/api/v1/service-accounts
/api/v1/api-keys
/api/v1/webhooks

Reuse existing routes/services when possible.

==================================================
2. PRINCIPALS
==================================================

Support:

HUMAN_USER
SERVICE_ACCOUNT
AGENT
SYSTEM

Do not reuse administrator credentials for integrations.

==================================================
3. SERVICE ACCOUNTS
==================================================

Implement ServiceAccount:

id
organization_id
name
description
status
created_by
created_at
updated_at

Examples:

Conciencia
Marketing Bot
Finance Sync
Telegram Bot

==================================================
4. API KEYS
==================================================

Implement secure API keys.

Requirements:

- cryptographically secure generation
- recognizable prefix, e.g. lt_live_
- show full key only once
- NEVER store plaintext
- store secure hash
- store prefix
- expiration
- revocation
- last_used_at
- audit creation/revocation/use

==================================================
5. SCOPES
==================================================

Examples:

organization:read
departments:read
members:read

workitems:read
workitems:create
workitems:update
workitems:assign
workitems:transition
workitems:comment

approvals:read
approvals:request
approvals:decide

analytics:read
webhooks:manage

Do not default to full access.

==================================================
6. ORGANIZATION ISOLATION
==================================================

Every request must be scoped to an organization.

A service account from Organization A must never access Organization B.

Enforce server-side.

==================================================
7. WORK ITEMS
==================================================

GET /work-items must support:

status
workflow
department
assignee
priority
type
project
branch
overdue
created_after
updated_after

Add pagination and sorting.

POST /work-items must use existing domain/application services.

==================================================
8. TRANSITIONS
==================================================

POST /api/v1/work-items/{id}/transition

must validate:

current state
allowed transition
permissions
approvals
deliverables
dependencies
workflow rules

Never bypass the Workflow Engine.

==================================================
9. AGENT SAFETY
==================================================

Agents/service accounts must use the same authorization boundaries as humans.

Start with:

READ
SEARCH
SUMMARIZE

Then:

CREATE
COMMENT
PROPOSE

High-impact actions require explicit scopes and, where appropriate, human approval.

==================================================
10. IDEMPOTENCY
==================================================

Support Idempotency-Key on mutation endpoints.

At minimum:

WorkItem creation
comments
sensitive workflow mutations

Retries must not create duplicates.

==================================================
11. REQUEST IDs
==================================================

Generate or accept X-Request-ID.

Return and log it.

==================================================
12. WEBHOOKS
==================================================

Implement outgoing webhooks.

Events:

work_item.created
work_item.updated
work_item.assigned
work_item.transitioned
work_item.completed
work_item.overdue

comment.created

approval.requested
approval.approved
approval.rejected

deliverable.submitted

Sign payloads using HMAC.

Include:

X-LinTeam-Event
X-LinTeam-Delivery
X-LinTeam-Timestamp
X-LinTeam-Signature

Persist attempts and retry asynchronously with backoff.

==================================================
13. AUDIT
==================================================

Audit actor types:

HUMAN
SERVICE_ACCOUNT
AGENT
SYSTEM

Capture where appropriate:

service_account_id
api_key_id
request_id
source=API
action
entity
timestamp

Never log plaintext API keys.

==================================================
14. OPENAPI
==================================================

Improve:

/docs
/openapi.json

Use clear tags, schemas and stable error codes.

Example error:

{
  "error": {
    "code": "WORKFLOW_TRANSITION_NOT_ALLOWED",
    "message": "...",
    "request_id": "..."
  }
}

==================================================
15. CONCURRENCY
==================================================

Protect WorkItems from concurrent overwrites.

Reuse existing version/concurrency controls where available.

Return 409 on conflicts.

==================================================
16. CONCIENCIA CONNECTOR CONTRACT
==================================================

Document recommended operations:

GET current work
GET overdue work
GET department status
SEARCH WorkItems
GET WorkItem detail
CREATE WorkItem
COMMENT
PROPOSE/EXECUTE transition according to scope
LIST approvals
GET organizational summary

Conciencia must not depend on LINTEAM database schemas.

==================================================
17. ADMIN UI
==================================================

Add:

/app/admin/integrations

Sections:

Service Accounts
API Keys
Webhooks

Allow:

create service account
create API key
show full key once
view prefix/scopes/expiration/last used
revoke
create/disable webhook
inspect deliveries

==================================================
18. TESTS
==================================================

Test:

valid API key
invalid key
revoked key
expired key
scope denied
cross-organization access denied
agent cannot bypass workflow
idempotent WorkItem creation
idempotency conflict
webhook HMAC
webhook retries
audit attribution
rate limiting

==================================================
19. INTEGRATION TEST
==================================================

Scenario:

1. Admin creates Service Account "Conciencia".
2. Admin creates read-only key.
3. Key lists departments.
4. Key queries WorkItems.
5. Create attempt is denied.
6. Admin grants workitems:create.
7. Conciencia creates WorkItem.
8. Audit identifies Conciencia.
9. Webhook is queued.
10. Retry with same Idempotency-Key creates no duplicate.
11. Unauthorized transition is rejected.
12. Human sees WorkItem in React Pipeline.

==================================================
20. DOCUMENTATION
==================================================

Create:

docs/api/API_OVERVIEW.md
docs/api/AUTHENTICATION.md
docs/api/API_KEYS.md
docs/api/SCOPES.md
docs/api/WEBHOOKS.md
docs/integrations/CONCIENCIA.md

Use placeholder credentials only.

==================================================
FINAL ACCEPTANCE
==================================================

Complete when:

[ ] service accounts authenticate
[ ] keys are hashed and shown once
[ ] scopes are enforced
[ ] organization isolation works
[ ] WorkItems are exposed through /api/v1
[ ] authorized integrations can create WorkItems
[ ] workflow rules cannot be bypassed
[ ] idempotency prevents duplicates
[ ] webhooks are signed and async
[ ] API actions appear in audit
[ ] OpenAPI is accurate
[ ] admin can manage integration credentials
[ ] Conciencia connects without database access

First inspect the existing auth/API/audit/workflow implementation and reuse
what already works.

Do not duplicate architecture.
