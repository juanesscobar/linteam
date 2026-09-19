You are working on LINTEAM.

Repository:
https://github.com/juanesscobar/linteam

Production:
https://linteam.online

STACK
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- React 19
- TypeScript
- Vite
- TanStack Query
- Dokploy / Contabo

LINTEAM is a real operational system for company work.

It is the system of record for:
- organizations
- departments
- employees/users
- work items/tasks
- workflows
- assignments
- comments
- approvals
- notifications
- audit
- integrations

Existing architecture may already contain:
- notification work from a previous phase
- service accounts
- API keys/scopes
- audit attribution
- idempotency
- integration boundaries
- WhatsApp-related placeholders/settings
- external API routes

IMPORTANT:
Inspect the CURRENT repository before assuming any of these are implemented exactly as described.

============================================================
MISSION
============================================================

Implement:

LINTEAM AGENT — PHASE 01

with Telegram as the first bidirectional communication channel.

This is NOT merely a Telegram bot.

Build a channel-independent LINTEAM Agent capable of safely interacting with
LINTEAM's existing application/domain layer.

Telegram is the first adapter.

Future adapters may include:

- LINTEAM web UI
- Email
- WhatsApp
- Slack
- Microsoft Teams
- Conciencia
- CLI

Architecture:

                   LINTEAM
              System of Record
                     |
              Application Layer
                     |
               LINTEAM Agent
          identity / authorization
           intent / commands / audit
                     |
             Channel Adapters
              /             \
        Telegram          future
                           channels


PRODUCT PRINCIPLE:

LINTEAM remains the source of truth.

The agent is an operational interface into LINTEAM.

Never create a second task database.
Never create independent agent memory containing authoritative business state.
Never let Telegram directly mutate PostgreSQL.

============================================================
0. SAFETY / PRODUCTION RULES
============================================================

Production is live.

DO NOT:

- reset PostgreSQL
- recreate the database
- delete volumes
- run destructive migrations manually
- modify production data manually
- modify Dokploy directly
- expose PostgreSQL
- commit secrets
- commit bot tokens
- hardcode credentials
- redeploy production
- docker compose down production
- use global docker prune
- force push
- overwrite unrelated local changes

Do not run long-running foreground processes that may hang the coding agent.

Implement and validate code only.

Production deployment will be performed manually later.

============================================================
1. REPOSITORY DISCOVERY FIRST
============================================================

Before changing anything, inspect:

BACKEND
- current package structure
- work-item application services
- authentication
- authorization/RBAC
- organization boundaries
- users
- departments
- assignments
- comments
- transitions
- audit
- notification implementation
- integrations
- service accounts
- API keys
- idempotency
- configuration/settings
- background jobs if any
- existing webhook infrastructure
- existing WhatsApp code/placeholders
- Alembic migration history

FRONTEND
- navigation
- current notification UI
- user settings/profile
- integration/admin pages
- task detail UI
- existing command/search interfaces

TESTS
- backend testing conventions
- frontend testing conventions

Do not redesign working architecture unnecessarily.

Produce a concise implementation plan before editing.

============================================================
2. CORE DESIGN — LINTEAM AGENT
============================================================

Create a channel-independent application service.

Suggested conceptual interface:

LinteamAgentService

Responsibilities:

- resolve authenticated actor
- receive structured agent request
- understand supported intent
- validate parameters
- enforce authorization
- call existing LINTEAM application services
- return structured response
- generate audit attribution
- require confirmation for sensitive actions where appropriate

DO NOT put Telegram logic inside this service.

Example:

Telegram Update
      |
TelegramAdapter
      |
AgentRequest
      |
LinteamAgentService
      |
existing WorkItemService
      |
PostgreSQL


Suggested internal request:

AgentRequest
- actor_user_id
- organization_id
- channel
- channel_identity
- text
- optional structured command
- correlation_id
- external_message_id

Suggested response:

AgentResponse
- text
- status
- action
- entity_type
- entity_id
- requires_confirmation
- optional actions/buttons

Adapt naming to existing project conventions.

============================================================
3. DO NOT REQUIRE AN LLM FOR BASIC OPERATIONS
============================================================

The agent must work WITHOUT an LLM.

Implement deterministic commands/intents first.

Examples:

/start
/help
/tasks
/today
/overdue
/assigned
/task <id>
/done <id>
/comment <id> <text>

Also support simple Spanish aliases if architecture permits.

Examples:

"mis tareas"
"tareas de hoy"
"tareas atrasadas"

Do NOT build an uncontrolled natural-language autonomous agent.

Design an optional future:

AgentIntentResolver

with:

DeterministicIntentResolver
LLMIntentResolver (future/optional)

Business actions must always execute through validated structured commands.

An LLM must never directly execute arbitrary SQL or tools.

============================================================
4. PHASE 01 SUPPORTED READ OPERATIONS
============================================================

Implement:

A. MY TASKS

/tasks

Return assigned open work items.

B. TODAY

/today

Return tasks relevant/due today.

C. OVERDUE

/overdue

Return overdue work items accessible to actor.

D. TASK DETAIL

/task <identifier>

Return concise:

- title
- status
- priority
- assignee
- due date
- department/project if applicable
- link to LINTEAM

E. HELP

/help

Return available capabilities.

Keep Telegram responses concise.

Avoid dumping dozens of tasks.

If result is large:
- limit
- paginate
- provide "Open LINTEAM" link

============================================================
5. PHASE 01 WRITE OPERATIONS
============================================================

Implement carefully:

A. COMPLETE TASK

/done <task-id>

Flow:

Telegram
→ identity
→ permission check
→ fetch task
→ validate allowed transition
→ confirmation
→ existing WorkItem application service
→ audit
→ response

Prefer confirmation button:

"Marcar 'Preparar informe' como completada?"

[Confirmar] [Cancelar]

Do NOT directly set database status.

Use existing workflow/transition rules.

B. COMMENT

/comment <task-id> <text>

Use existing comment application service.

C. CREATE TASK

/create

For Phase 01 implement a controlled flow.

Example:

User:
/create

Bot:
"¿Cuál es el título de la tarea?"

User:
"Preparar informe mensual"

Bot:
"¿A quién querés asignarla?"

Then:
- select user if authorized
- optional due date
- optional priority

Finally show:

Nueva tarea

Título: Preparar informe mensual
Responsable: María
Vence: mañana
Prioridad: Normal

[Crear tarea] [Cancelar]

Only create after confirmation.

If implementing conversational state would substantially complicate Phase 01,
a structured command is acceptable initially:

/create "Preparar informe mensual"

Then use Telegram buttons / web UI link for remaining fields.

Choose the smallest robust implementation.

============================================================
6. TELEGRAM IDENTITY LINKING
============================================================

CRITICAL:

Never trust a Telegram username as LINTEAM identity.

Implement explicit account linking.

Suggested model:

communication_identities

- id
- organization_id
- user_id
- channel
- external_user_id
- external_chat_id nullable
- username/display_name nullable informational only
- verified_at
- enabled
- created_at
- updated_at

Unique constraints must prevent unsafe duplicate identity mapping.

Channel enum:

TELEGRAM
EMAIL
WHATSAPP
...

Telegram numeric user ID is authoritative after linking.

============================================================
7. SECURE ACCOUNT LINKING FLOW
============================================================

Implement a secure short-lived linking mechanism.

Preferred flow:

Inside authenticated LINTEAM:

Settings
→ Communication Channels
→ Connect Telegram

LINTEAM creates:

- single-use token
- cryptographically random
- short expiration
- stored hashed if practical

Generate deep link:

https://t.me/<bot_username>?start=<link_token>

User opens Telegram.

Bot receives:

/start <token>

Backend:

- validates token
- verifies unused
- verifies expiration
- binds Telegram user ID to LINTEAM user
- consumes token
- audit event

Telegram replies:

"Tu cuenta de Telegram quedó vinculada a LINTEAM."

Do NOT expose permanent API keys through Telegram.

Do NOT use email/name matching for authentication.

============================================================
8. TELEGRAM BOT / WEBHOOK
============================================================

Use Telegram Bot API.

Production architecture should use WEBHOOKS, not permanent polling.

Configuration examples:

LINTEAM_TELEGRAM_ENABLED=false
LINTEAM_TELEGRAM_BOT_TOKEN=
LINTEAM_TELEGRAM_BOT_USERNAME=
LINTEAM_TELEGRAM_WEBHOOK_SECRET=
LINTEAM_TELEGRAM_WEBHOOK_URL=

No real values in repository.

Suggested endpoint:

POST /api/v1/integrations/telegram/webhook

or adapt to existing integration routing.

Validate Telegram webhook secret using Telegram's supported secret-token header.

Reject invalid webhook requests.

Never log bot token.

Never return secrets.

Handle Telegram retries idempotently.

Use update_id and/or message identifiers to prevent duplicate actions.

============================================================
9. TELEGRAM ADAPTER
============================================================

Implement a Telegram adapter/provider separated from agent core.

Conceptually:

TelegramChannelAdapter

Responsibilities:

- parse Telegram Update
- identify sender
- translate message → AgentRequest
- render AgentResponse → Telegram message
- inline keyboard/buttons
- send/edit messages
- callback query handling
- deep-link account linking

It must NOT contain work-item business rules.

============================================================
10. NOTIFICATION INTEGRATION
============================================================

Inspect the notification architecture already implemented.

Do not create a parallel notification system.

Add TELEGRAM as a notification delivery provider/channel.

Conceptually:

NotificationService
      |
      +-- InAppProvider
      +-- EmailProvider
      +-- TelegramProvider
      +-- WhatsAppProvider (future/disabled)

Telegram notifications should initially support:

- work item assigned
- work item reassigned
- important status change
- due soon
- overdue
- comment/mention when appropriate

Avoid notification spam.

============================================================
11. TELEGRAM NOTIFICATION FORMAT
============================================================

Example:

LINTEAM · Nueva tarea

Preparar informe de cobranzas

Prioridad: Alta
Vence: Hoy 17:00
Asignada por: José

[Ver tarea] [Mis tareas]

Link:

https://linteam.online/...

Use existing task routing.

Do not use linteam.linteam.online.

============================================================
12. NOTIFICATION DELIVERY RULES
============================================================

Telegram delivery requires:

- TELEGRAM enabled globally
- user has linked Telegram identity
- identity enabled
- user preference allows Telegram notifications

If unavailable:

delivery status -> SKIPPED

Reason should be machine-readable where appropriate.

Telegram delivery failure MUST NOT fail task creation/update.

Persist delivery state using existing notification delivery architecture.

============================================================
13. TELEGRAM USER PREFERENCES
============================================================

Extend existing notification preferences if present.

Add:

telegram_enabled

Potential UI:

Settings
→ Notifications

In-app     ON
Email      ON/OFF
Telegram   ON/OFF

Communication Channels:

Telegram
Connected as @username
[Disconnect]

or:

Telegram
Not connected
[Connect Telegram]

Username is display-only.
Telegram numeric ID remains authoritative.

============================================================
14. LINTEAM AGENT WEB UI
============================================================

Expose the same agent inside LINTEAM.

Do NOT build another generic ChatGPT clone.

Create a lightweight operational interface.

Possible entry point:

"LINTEAM Agent"

or command palette integration if current UX has one.

Capabilities:

- Mis tareas
- Tareas de hoy
- Atrasadas
- Crear tarea
- Buscar tarea
- Completar tarea
- Añadir comentario

Prefer action-oriented UI.

Examples:

"¿Qué necesita atención hoy?"

Result:

3 tareas requieren atención

[Preparar informe]
Hoy · Alta

[Revisar contrato]
Vencida · Alta

[Ver todas]

The web agent MUST use the same:

LinteamAgentService

as Telegram.

No duplicated business logic.

============================================================
15. AGENT AUTHORIZATION
============================================================

Agent permissions are NEVER broader than actor permissions.

Examples:

Employee:
- own/authorized tasks

Manager:
- department/team scope according to existing RBAC

Admin:
- existing admin scope

Telegram does not create new privileges.

For every write:

identity
→ organization
→ actor
→ permission
→ application service
→ audit

============================================================
16. AUDIT
============================================================

Agent actions must be attributable.

Audit should capture where appropriate:

actor_user_id
organization_id
channel = TELEGRAM / WEB
action
entity
entity_id
correlation_id

Example:

WORK_ITEM_STATUS_CHANGED
actor: user 123
channel: TELEGRAM
source: LINTEAM_AGENT

Never attribute Telegram actions to a generic bot when a linked human performed
the action.

System-generated notifications can use SYSTEM attribution.

============================================================
17. IDEMPOTENCY
============================================================

Telegram retries webhook updates.

Prevent duplicate:

- task creation
- status changes
- comments
- confirmations

Persist/process Telegram update_id or use existing idempotency infrastructure.

Callback buttons must also be safe against repeated clicks.

============================================================
18. CONVERSATIONAL STATE
============================================================

If multi-step /create is implemented, keep state minimal.

Do not create open-ended memory.

Suggested:

agent_sessions

or existing equivalent:

- actor
- channel
- conversation_id
- pending_intent
- structured state JSON
- expires_at

TTL should be short.

State is workflow state, NOT long-term AI memory.

Cancel:

/cancel

must clear pending operation.

============================================================
19. OPTIONAL LLM BOUNDARY
============================================================

Prepare architecture for a future natural-language resolver.

DO NOT require an LLM for Phase 01.

Future:

User:
"creale una tarea a María para revisar el contrato mañana"

LLM:
→ structured proposal

{
  "intent": "CREATE_WORK_ITEM",
  "title": "Revisar contrato",
  "assignee": "...",
  "due_date": "...",
  "confidence": ...
}

Then:

authorization
validation
confirmation
application service
audit

LLM output is UNTRUSTED INPUT.

Never execute an LLM-generated command without schema validation and permission
checks.

============================================================
20. TELEGRAM CLIENT
============================================================

Implement a small async Telegram Bot API client using existing HTTP tooling
(httpx if already present).

Required operations likely include:

- sendMessage
- answerCallbackQuery
- editMessageText if needed
- setWebhook helper/service if appropriate

Do not introduce a heavy Telegram framework unless justified.

Prefer a thin adapter around Telegram Bot API.

============================================================
21. DATABASE MIGRATIONS
============================================================

Create additive Alembic migration(s) only.

Potential additions:

communication_identities
communication_link_tokens
processed_channel_events
agent_sessions (only if required)

and extensions to notification preferences/delivery enums if needed.

Do not modify old migrations.

Validate migration chain.

Do not run destructive production migration manually.

============================================================
22. API / FRONTEND
============================================================

Add authenticated endpoints as appropriate:

GET /api/v1/me/communication-channels
POST /api/v1/me/communication-channels/telegram/link
DELETE /api/v1/me/communication-channels/telegram

Agent endpoint for web UI, e.g.:

POST /api/v1/agent/execute

Use existing API conventions.

Do not expose Telegram bot token to frontend.

============================================================
23. TELEGRAM BOT CREATION DOCUMENTATION
============================================================

Create:

docs/TELEGRAM_AGENT_PHASE_01.md

Document manual setup using BotFather:

1. create bot
2. obtain token
3. configure username
4. add token to production environment
5. generate webhook secret
6. configure webhook URL
7. register webhook
8. verify webhook
9. connect first LINTEAM account
10. smoke test

DO NOT include real credentials.

Document expected production webhook:

https://linteam.online/api/v1/integrations/telegram/webhook

if that matches actual routing.

============================================================
24. TESTING
============================================================

Backend tests:

IDENTITY
- valid link token
- expired token rejected
- reused token rejected
- duplicate Telegram identity rejected
- username cannot authenticate user

WEBHOOK
- invalid webhook secret rejected
- valid update accepted
- duplicate update idempotent

AGENT READS
- /tasks
- /today
- /overdue
- /task

AUTHORIZATION
- user cannot access unauthorized task
- organization boundary enforced

WRITES
- /done requires/uses valid transition
- confirmation required
- repeated callback does not duplicate mutation
- /comment uses existing service
- create flow validates permissions

NOTIFICATIONS
- linked Telegram user receives eligible notification
- unlinked user -> skipped
- disabled preference -> skipped
- provider failure does not fail work-item mutation

AUDIT
- Telegram action attributed to linked human actor
- channel/source recorded

Frontend tests:

- communication settings render
- connect Telegram action
- disconnect
- Telegram preference
- basic LINTEAM Agent interface
- successful agent operation refreshes relevant queries

============================================================
25. VALIDATION
============================================================

Run targeted tests first.

Then run the existing full relevant test suites.

Validate:

- backend tests
- frontend tests
- frontend build
- lint/typecheck if configured
- Alembic migration chain
- git diff --check

Do not start blocking production servers.

Do not redeploy Dokploy.

============================================================
26. OBSERVABILITY
============================================================

Add structured logging for:

- webhook accepted/rejected
- update processed
- agent intent selected
- action success/failure
- Telegram delivery failure

Never log:

- bot token
- link token
- webhook secret
- sensitive message content unnecessarily

Use correlation/update IDs.

============================================================
27. DOCUMENT FUTURE PHASES
============================================================

Document but do not implement broadly:

PHASE 02
Natural-language intent resolver.

Examples:

"qué tengo pendiente hoy?"
"creale una tarea a Pedro para mañana"
"avisa al equipo de administración"

PHASE 03
Email conversational/action links.

PHASE 04
WhatsApp Business adapter when available.

PHASE 05
Conciencia integration.

Important future architecture:

Conciencia
→ LINTEAM Agent/API
→ permission/scopes
→ application services
→ audit

Never direct database access.

============================================================
28. FINAL REPORT
============================================================

At completion report:

1. Architecture discovered
2. Agent architecture implemented
3. Telegram adapter implemented
4. Identity-linking design
5. Supported commands
6. Supported write operations
7. Confirmation model
8. Notification integration
9. Web agent UI
10. Database migrations
11. Security controls
12. Idempotency strategy
13. Tests added
14. Test/build results
15. Required environment variables
16. BotFather/manual steps
17. Deployment procedure
18. Risks/limitations
19. Deferred Phase 02 items
20. Files changed
21. Commit SHA

============================================================
29. GIT
============================================================

Before commit:

git status
git diff
git diff --check

Preserve unrelated changes.

Do not commit:
- linteam.db
- .env
- credentials
- bot tokens
- generated local junk

Suggested commit:

feat: add linteam agent with telegram integration

Push normally to current branch only after tests pass.

Never force push.

============================================================
DEFINITION OF DONE
============================================================

Phase 01 is done when:

1. A logged-in LINTEAM user can securely link Telegram.
2. Telegram numeric identity maps securely to that user.
3. /tasks returns authorized tasks.
4. /today works.
5. /overdue works.
6. /task works.
7. A safe write action such as /done works through confirmation.
8. Task creation has a controlled confirmed flow or clearly documented minimal
   Phase 01 implementation.
9. Telegram can deliver LINTEAM task notifications.
10. Telegram failures never break task operations.
11. All actions respect existing RBAC/org boundaries.
12. Agent actions are auditable.
13. Duplicate Telegram updates cannot duplicate mutations.
14. LINTEAM web UI exposes the same agent capability without duplicating business
    logic.
15. No production secrets are committed.
16. Tests/build pass.
17. Production has NOT been redeployed automatically.

FINAL PRINCIPLE:

Do not build a Telegram bot that happens to talk to LINTEAM.

Build the LINTEAM Agent.

Telegram is only its first communication adapter.

LINTEAM remains the authoritative operational system.