LINTEAM — PILOT 01 RUNTIME CLOSEOUT

Do not implement new product features.

The integration layer already exists.

Your only objective is to make the existing backend integration pilot
actually execute and produce reliable runtime evidence.

Current implemented state:

- X-API-Key SERVICE_ACCOUNT authentication
- API keys / service accounts
- GET /api/v1/me
- stable paginated GET /api/v1/work-items:
  {items, page, page_size, total}
- organization/effective scope information in /me
- idempotency
- audit/request metadata
- Conciencia HTTP client:
  app/integrations/conciencia_client.py
- API key/revocation/expiration/me/pagination/idempotency tests
- frontend build PASS
- git diff --check PASS

Backend runtime validation is still incomplete.

==================================================
1. DO NOT ADD FEATURES
==================================================

No new UI features.
No new domain entities.
No agent write capabilities.

Close Pilot 01 only.

==================================================
2. USE DOCKER AS CANONICAL RUNTIME
==================================================

Do not depend on the broken local Windows Python launcher.

Inspect:

docker compose config
docker compose ps
docker version
docker info

Fix Compose/Dockerfile only if required to get a deterministic dev/test
runtime.

==================================================
3. BUILD
==================================================

Run:

docker compose build --no-cache app

Capture whether it succeeds.

If it fails, identify the first real failure.

Do not summarize generic Docker output.

Fix the root cause.

==================================================
4. STARTUP
==================================================

Run:

docker compose up -d

Then verify:

docker compose ps
docker compose logs app --tail=200

Application must start without traceback.

==================================================
5. HEALTH
==================================================

Verify:

GET /ready or /health
GET /openapi.json
GET /app/

All must return correctly.

==================================================
6. MIGRATIONS
==================================================

Run the repository's canonical migration command.

Verify tables exist for:

service_accounts
api_keys
webhooks
webhook_deliveries
idempotency_records

Migration must succeed from a clean dev database.

Do not rely on create_all as a substitute if Alembic is the project's
migration mechanism.

==================================================
7. BACKEND TESTS
==================================================

Execute the backend test suite inside Docker.

Prefer:

docker compose exec app python -m pytest -q

or a dedicated test container/target if dependencies require it.

Do not claim PASS if tests were only statically inspected.

Report:

passed
failed
skipped
duration

==================================================
8. GET_SESSION REGRESSION
==================================================

Review the recent change where get_session():

- commits on successful request
- rolls back on exception

Validate that this does not introduce unintended commits.

Search for application/domain services that already:

commit
rollback
begin transactions

Ensure there is one coherent transaction boundary.

Add regression tests where needed.

Important cases:

WorkItem creation
comments
workflow transition
API key last_used_at
audit writes
failed request rollback

==================================================
9. HUMAN AUTH REGRESSION
==================================================

Verify existing JWT/human authentication still works.

Machine auth must not replace or alter human semantics.

==================================================
10. SERVICE ACCOUNT PILOT
==================================================

Create a development Service Account:

Conciencia

Read-only scopes only:

organization:read
departments:read
workitems:read

Generate an API key.

Never store or document the plaintext secret.

==================================================
11. LIVE API TEST
==================================================

With the real running backend, verify:

GET /api/v1/me

GET /api/v1/departments

GET /api/v1/work-items

GET /api/v1/work-items?page=1&page_size=...

using X-API-Key.

Verify:

principal_type = SERVICE_ACCOUNT
organization_id correct
effective_scopes correct
pagination correct

==================================================
12. DENIAL TESTS
==================================================

Using the read-only Conciencia key:

POST work item
POST comment
POST transition

must fail with 403.

Also verify:

invalid key -> 401
expired key -> 401
revoked key -> 401
cross-org resource -> safe 403/404

==================================================
13. IDEMPOTENCY LIVE TEST
==================================================

Using a temporary mutation-capable test service account in dev:

send same WorkItem create request twice with same Idempotency-Key.

Expected:

one WorkItem
same logical response

Then reuse the same key with a different payload.

Expected:

409 conflict or documented equivalent.

==================================================
14. AUDIT LIVE TEST
==================================================

Verify a real API-key request produces audit metadata containing:

principal_type
service_account_id
organization_id
request_id
source
action
entity

Verify plaintext API key is absent from:

database
logs
audit
exceptions

==================================================
15. CONCIENCIA CLIENT DOGFOOD
==================================================

Execute:

ConcienciaClient.get_me()
ConcienciaClient.list_departments()
ConcienciaClient.list_work_items()
ConcienciaClient.get_overdue_work()

against the running LINTEAM backend.

This must be a real HTTP call.

Do not mock the final dogfood test.

==================================================
16. RESULT
==================================================

Update:

docs/integrations/PILOT_01_REPORT.md

with actual runtime evidence.

Every row must be one of:

PASS
FAIL
NOT READY

Do not convert NOT READY to PASS based on implementation alone.

Include exact commands executed and concise outputs.

Never include credentials.

==================================================
FINAL ACCEPTANCE
==================================================

Pilot 01 is green only when:

- Docker backend starts
- migrations pass
- backend tests pass
- human JWT regression passes
- API key auth runs live
- scopes run live
- organization isolation runs live
- pagination runs live
- idempotency runs live
- audit runs live
- ConcienciaClient performs real HTTP read-only requests

No further feature development until these conditions are met.
