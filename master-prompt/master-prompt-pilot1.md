LINTEAM — INTEGRATION PILOT 01
BACKEND VALIDATION + CONCIENCIA READ-ONLY DOGFOOD

You have implemented the initial LINTEAM machine-to-machine integration layer.

Do NOT add major new features.

The goal of this iteration is to PROVE that the integration architecture
actually works end-to-end in a real backend runtime.

Current reported implementation includes:

- X-API-Key authentication for SERVICE_ACCOUNT principals
- existing human JWT authentication preserved
- service_accounts
- api_keys
- webhooks
- webhook_deliveries
- idempotency_records
- request/principal-aware audit metadata
- idempotency for WorkItem creation, comments and transitions
- GET /api/v1/me
- GET /api/v1/organizations
- filtered/paginated GET /api/v1/work-items
- POST /api/v1/work-items/{id}/transition
- integration administration endpoints
- React AdminIntegrationsPage
- docs/api/*
- docs/integrations/CONCIENCIA.md

Frontend build and git diff --check passed.

Backend validation has NOT yet been completed.

==================================================
PRIMARY OBJECTIVE
==================================================

Turn the current implementation into a validated:

LINTEAM INTEGRATION PILOT 01

The pilot must prove:

SERVICE ACCOUNT
→ API KEY
→ AUTHENTICATION
→ ORGANIZATION ISOLATION
→ SCOPE AUTHORIZATION
→ DOMAIN SERVICE
→ RESPONSE
→ AUDIT

Do not mark PASS based only on code inspection.

==================================================
1. ESTABLISH A USABLE BACKEND RUNTIME
==================================================

Inspect the repository environment.

Prefer the existing Docker/Compose environment when available.

Do not depend on the broken Windows Store Python launcher.

If Docker is available:

build and run the backend there.

If runtime permissions block Docker, document the exact blocker and still
perform every validation possible statically.

Do not silently skip backend validation.

==================================================
2. DATABASE MIGRATIONS
==================================================

Verify migrations exist for:

service_accounts
api_keys
webhooks
webhook_deliveries
idempotency_records

Run migrations against a disposable/dev database.

Verify:

upgrade succeeds

application starts

schema matches SQLAlchemy models

no missing imports

no circular imports

no startup exceptions

==================================================
3. APPLICATION STARTUP
==================================================

Run LINTEAM.

Verify:

/health or /ready

/docs

/openapi.json

React frontend

API

all start together.

No traceback is acceptable.

==================================================
4. HUMAN AUTH REGRESSION
==================================================

Machine authentication must NOT break human authentication.

Test:

human login
JWT request
logout/session expiration
existing WorkItem access

Existing JWT behavior must remain valid.

==================================================
5. SERVICE ACCOUNT CREATION
==================================================

Through the proper admin application/service/API:

create:

Service Account:
Conciencia

Organization:
Lin Group

Initial scopes:

organization:read
departments:read
members:read
workitems:read
analytics:read

Do NOT initially grant:

workitems:create
workitems:update
workitems:transition
approvals:decide
admin scopes

==================================================
6. API KEY SECURITY
==================================================

Create an API key for Conciencia.

Verify:

full secret shown ONCE

database does NOT contain plaintext key

only hash/prefix/metadata stored

key has appropriate entropy

last_used_at works

revocation works

expiration works

audit records creation/revocation

Never print the real full key in reports or committed files.

Use placeholders in documentation.

==================================================
7. AUTHENTICATION TEST MATRIX
==================================================

Test:

VALID API KEY
→ authenticated

INVALID API KEY
→ 401

MALFORMED API KEY
→ 401

REVOKED API KEY
→ 401

EXPIRED API KEY
→ 401

MISSING API KEY
→ normal auth boundary

No stack traces.

Use stable error codes.

==================================================
8. /api/v1/me
==================================================

With Conciencia API key:

GET /api/v1/me

must clearly identify:

principal_type = SERVICE_ACCOUNT

service_account identity

organization

effective scopes

Do not pretend the service account is a human User.

==================================================
9. ORGANIZATION ISOLATION
==================================================

This is critical.

A key belonging to Lin Group must never access another organization.

Test every relevant query with another organization ID/entity.

Expected:

403 or safe 404 according to the application's security policy.

Never leak existence through overly detailed errors.

==================================================
10. SCOPE ENFORCEMENT
==================================================

Using the read-only Conciencia key:

GET WorkItems
→ PASS

GET departments
→ PASS

GET organization
→ PASS

POST WorkItem
→ MUST FAIL 403

POST comment
→ MUST FAIL 403

POST transition
→ MUST FAIL 403

Approval decision
→ MUST FAIL 403

Do not trust route decorators alone.

Verify service/domain authorization boundary.

==================================================
11. WORK ITEM QUERY
==================================================

Validate:

GET /api/v1/work-items

with:

pagination
status
department
assignee
priority
type
workflow
overdue
created_after
updated_after
sorting

Verify organization scoping is automatic.

Caller must not be able to override organization arbitrarily.

==================================================
12. PAGINATION CONTRACT
==================================================

Define and validate a stable pagination format.

Example:

{
  "items": [...],
  "page": 1,
  "page_size": 50,
  "total": 123
}

or cursor-based equivalent.

Do not return unbounded collections.

Document the chosen contract.

==================================================
13. TRANSITION ENDPOINT
==================================================

Verify:

POST /api/v1/work-items/{id}/transition

does NOT implement workflow logic independently.

It must call the existing canonical application/domain Workflow transition
service.

The same transition rules must apply whether called from:

React
human API
service account
Conciencia
future Telegram adapter

There must be ONE source of truth.

==================================================
14. IDEMPOTENCY
==================================================

Validate idempotency behavior using a service account that temporarily has
the required mutation scope in a controlled dev scenario.

For WorkItem creation:

Request A:

Idempotency-Key:
pilot-01-create-001

payload:
X

Repeat exact request.

Expected:

one WorkItem only
same logical response

Then:

same Idempotency-Key
different payload

Expected:

409 IDEMPOTENCY_CONFLICT

or equivalent stable error.

Repeat for:

comment creation

transition

where implemented.

==================================================
15. CONCURRENCY
==================================================

If WorkItem optimistic concurrency/versioning already exists, preserve it.

Test conflicting mutation.

Expected:

409 conflict

Do not allow idempotency to bypass optimistic concurrency protections.

==================================================
16. AUDIT ATTRIBUTION
==================================================

Every machine action must make it possible to determine:

actor_type = SERVICE_ACCOUNT

service_account_id

api_key_id or safe reference

organization_id

request_id

source = API

action

entity

timestamp

Never store secret key material.

==================================================
17. REQUEST ID
==================================================

Verify:

X-Request-ID supplied by caller
→ validated/preserved when safe

No supplied ID
→ generated by LINTEAM

Response returns request identifier.

Logs and audit can correlate it.

==================================================
18. RATE LIMIT / ABUSE BOUNDARY
==================================================

Inspect whether machine API endpoints have rate limiting.

If already implemented, test it.

If not implemented, add a minimal architecture appropriate to the project.

Do not build a distributed enterprise rate-limit platform unnecessarily.

At minimum prevent obviously abusive API-key use.

==================================================
19. OPENAPI
==================================================

Verify /openapi.json accurately describes:

X-API-Key authentication

JWT authentication where relevant

/api/v1/me

organizations

work-items

transitions

integration administration endpoints

schemas

pagination

error responses

scopes if representable

Do not expose secret fields.

==================================================
20. REACT ADMIN INTEGRATIONS
==================================================

Complete integration into the existing React AppLayout.

Add authorized navigation:

Admin
→ Integraciones

Route:

/app/admin/integrations

Only authorized admins see it.

Do not expose this navigation to normal employees.

Page should allow:

Service Accounts

API Keys

Webhooks

For API keys:

create
show once
copy UX if supported
expiration
scopes
last used
revoke

Do not ever retrieve the full secret again.

==================================================
21. UI STATE
==================================================

AdminIntegrationsPage must have:

loading
error
empty
success

Confirm destructive operations:

revoke API key
disable webhook

Do not use browser alert().

==================================================
22. CONCIENCIA CLIENT
==================================================

Create a minimal reusable client or integration example.

Do NOT merge LINTEAM database logic into Conciencia.

Implement/document calls such as:

get_me()

list_departments()

list_work_items()

get_work_item()

get_overdue_work()

get_department_work()

Use HTTP API only.

Environment configuration:

LINTEAM_BASE_URL

LINTEAM_API_KEY

Never hardcode secrets.

==================================================
23. READ-ONLY DOGFOOD
==================================================

Using the Conciencia Service Account:

perform a real local/dev query:

"What WorkItems currently require attention?"

The integration layer should be able to derive information from:

GET /api/v1/work-items

without direct DB access.

No write operations in this pilot.

==================================================
24. OPTIONAL CONCIENCIA TOOL CONTRACT
==================================================

Prepare tool contracts for future orchestration:

linteam_me

linteam_work_list

linteam_work_inspect

linteam_overdue

linteam_department_status

Do not yet expose mutation tools unless the pilot is fully green.

==================================================
25. WEBHOOK VALIDATION
==================================================

If outgoing webhooks are implemented enough to execute:

create a test webhook

emit:

work_item.created

verify:

delivery created

payload signed

timestamp included

event ID unique

failed delivery retry behavior

No infinite retry.

If webhook dispatch is not complete, explicitly mark it NOT READY rather
than pretending PASS.

==================================================
26. SECURITY REVIEW
==================================================

Check for:

plaintext API keys

secret leakage in logs

secret leakage in audit

cross-org queries

scope bypass

admin endpoint exposure

mass assignment

unsafe filter fields

unbounded pagination

path traversal

unsafe webhook URLs / SSRF boundaries

improper error disclosure

Fix critical/high findings before completing pilot.

==================================================
27. TESTS
==================================================

Add automated backend tests for at minimum:

service account creation

API key authentication

invalid key

revoked key

expired key

plaintext secret not persisted

scope allow

scope deny

organization isolation

/api/v1/me attribution

WorkItem filtering

pagination

idempotent create

idempotency payload conflict

transition authorization

audit attribution

human JWT regression

webhook signature if ready

==================================================
28. FULL REGRESSION
==================================================

Run all existing backend tests.

Run frontend:

npm run build
typecheck
lint/tests where configured

Do not accept new regressions.

==================================================
29. PILOT REPORT
==================================================

Create:

docs/integrations/PILOT_01_REPORT.md

Use a concise PASS / FAIL / NOT READY matrix.

Example:

BACKEND STARTUP:                  PASS
DATABASE MIGRATIONS:              PASS
HUMAN JWT REGRESSION:             PASS
SERVICE ACCOUNT AUTH:             PASS
API KEY HASHING:                  PASS
KEY SHOWN ONCE:                   PASS
REVOKED KEY BLOCKED:              PASS
EXPIRED KEY BLOCKED:              PASS
ORG ISOLATION:                    PASS
SCOPES:                           PASS
READ-ONLY CONCIENCIA:             PASS
WORKITEM FILTERS:                 PASS
PAGINATION:                       PASS
IDEMPOTENCY:                      PASS
AUDIT ATTRIBUTION:                PASS
TRANSITION CANONICAL SERVICE:     PASS
WEBHOOK DELIVERY:                 PASS / NOT READY
ADMIN UI:                         PASS
OPENAPI:                          PASS
FULL REGRESSION:                  PASS

Include exact commands used and summarized results.

Never include real API secrets.

==================================================
30. FINAL RULE
==================================================

Do not add unrelated features.

Do not claim the integration layer is production-ready solely because code
was generated.

The objective is to validate one real integration path:

CONCIENCIA
→ X-API-Key
→ LINTEAM API
→ authorized organizational data
→ audit trail

with no database access and no production mutation.

Only after this Pilot 01 is green should mutation permissions be expanded.
