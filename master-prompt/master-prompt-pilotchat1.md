Continue LINTEAM Agent Phase 01 from the CURRENT working tree.

DO NOT restart the implementation.
DO NOT discard the existing changes.
DO NOT reset, checkout, clean, stash, or overwrite unrelated work.

CURRENT IMPLEMENTED STATE

The previous implementation already reports:

- deterministic LinteamAgentService
- /tasks
- /today
- /overdue
- /task
- /done with confirmation
- /comment
- verified Telegram identities
- single-use hashed linking tokens with expiration
- Telegram webhook protected by secret-token
- webhook idempotency using update_id
- human-user audit attribution including channel
- additive Alembic migration
- Telegram variables in .env.example
- docs/TELEGRAM_AGENT_PHASE_01.md
- basic agent test
- 14 backend tests passing
- single Alembic head
- existing frontend build passing

It intentionally did NOT commit or push because the working tree contains
unrelated changes and Phase 01 remains incomplete.

Your job now is to FINISH Phase 01.

============================================================
1. FIRST AUDIT THE CURRENT WORKING TREE
============================================================

Before editing:

git status --short
git diff --stat
git diff

Identify:

A. files belonging to LINTEAM Agent work
B. unrelated pre-existing modifications
C. untracked unrelated files

Never modify/revert/delete category B or C.

Inspect the implementation already created.

Do not duplicate:
- LinteamAgentService
- identity models
- webhook models
- migrations
- audit logic
- idempotency logic

Extend the existing implementation.

Give a concise gap analysis before editing.

============================================================
2. PRIMARY PHASE 01B OBJECTIVE
============================================================

Complete these missing areas:

A. real Telegram Bot API outbound client
B. webhook -> agent -> Telegram response end-to-end
C. Telegram notification provider
D. controlled /create flow
E. React UI for LINTEAM Agent
F. React UI for Telegram connection/preferences
G. complete security/integration tests
H. documentation and production setup instructions

At the end, Phase 01 should be usable after we manually configure a Telegram
bot and production environment variables.

DO NOT deploy production.

============================================================
3. TELEGRAM BOT API CLIENT
============================================================

Implement a thin async Telegram Bot API client.

Prefer httpx if already available.

Do not add a large Telegram framework unless absolutely necessary.

Conceptually:

TelegramBotClient

Support at minimum:

- send_message
- answer_callback_query
- edit_message_text if required by confirmation UX
- get_me for configuration/smoke validation if useful
- set_webhook helper if appropriate

Telegram API base:

https://api.telegram.org/bot<TOKEN>/...

BUT:

Never log the full URL when it contains the token.

Never expose token in errors.

Never send token to frontend.

Configuration must come from settings/environment.

Existing expected settings should be reused.

Likely:

LINTEAM_TELEGRAM_ENABLED
LINTEAM_TELEGRAM_BOT_TOKEN
LINTEAM_TELEGRAM_BOT_USERNAME
LINTEAM_TELEGRAM_WEBHOOK_SECRET
LINTEAM_TELEGRAM_WEBHOOK_URL

Do not hardcode production values.

============================================================
4. WEBHOOK -> AGENT -> RESPONSE
============================================================

Complete the actual runtime path:

Telegram Update
      ↓
webhook validation
      ↓
idempotency
      ↓
Telegram identity resolution
      ↓
LinteamAgentService
      ↓
AgentResponse
      ↓
TelegramBotClient
      ↓
Telegram user

Commands already implemented must actually return Telegram messages:

/help
/tasks
/today
/overdue
/task
/done
/comment

Handle:

- unknown command
- unlinked Telegram account
- disabled account
- malformed command
- unauthorized action
- nonexistent task
- provider/API failure

Responses should be concise and in Spanish.

Example:

LINTEAM · Mis tareas

1. Preparar informe
   Alta · vence hoy

2. Revisar contrato
   Normal · vence mañana

[Open LINTEAM]

Use:
https://linteam.online

Do not use:
linteam.linteam.online

============================================================
5. CALLBACK QUERIES / CONFIRMATION
============================================================

Complete Telegram inline keyboard confirmation.

Example:

/done 154

Bot:

¿Marcar esta tarea como completada?

Preparar informe mensual

[Confirmar] [Cancelar]

Callback must contain only safe opaque/validated information.

Do not trust callback payload blindly.

On confirm:

callback
→ identity
→ authorization
→ current task state
→ valid transition
→ existing application service
→ audit
→ result

Repeated callback must NOT duplicate mutation.

On success edit/respond:

✓ Tarea completada

Preparar informe mensual

[Ver en LINTEAM]

============================================================
6. IMPLEMENT CONTROLLED /create
============================================================

Add task creation to Phase 01.

Do NOT implement open-ended AI interpretation.

Preferred Telegram UX:

/create

Step 1:
¿Cuál es el título?

Step 2:
¿A quién querés asignarla?

Use allowed users visible to the actor.

Prefer Telegram inline buttons when result set is reasonably small.

Step 3:
¿Cuándo vence?

Provide simple options:

[Hoy]
[Mañana]
[Sin fecha]

and optionally:
[Otra fecha]

Step 4:
Prioridad:

[Baja]
[Normal]
[Alta]
[Urgente]

Reuse existing LINTEAM priority model.
Do not invent incompatible values.

Step 5 confirmation:

Nueva tarea

Título: Preparar informe
Responsable: María
Vence: Mañana
Prioridad: Alta

[Crear tarea]
[Cancelar]

ONLY after confirmation:

→ validate identity again
→ validate organization
→ validate permissions
→ call existing task creation service
→ audit
→ create notifications through existing notification system
→ respond with task link

Do not insert WorkItem ORM objects directly from Telegram code.

============================================================
7. CONVERSATIONAL WORKFLOW STATE
============================================================

Inspect whether the previous implementation already added session/workflow state.

Reuse it if present.

If not, implement the smallest safe persisted state required for /create.

State must contain structured workflow data only.

Example:

channel
external_user_id / linked user
pending_intent
step
payload JSON
expires_at

This is NOT AI memory.

Requirements:

- short TTL
- /cancel clears it
- successful creation clears it
- expired state ignored/deleted safely
- one actor cannot access another actor's state
- organization boundary
- malformed state fails safely

============================================================
8. TELEGRAM NOTIFICATION PROVIDER
============================================================

Integrate Telegram into the EXISTING notification architecture.

Do not create NotificationServiceV2.

Conceptually:

NotificationService
├── InApp
├── Email
├── Telegram  ← implement
└── future WhatsApp

TelegramNotificationProvider:

- resolves verified communication identity
- respects user preference
- sends through TelegramBotClient
- stores SENT / FAILED / SKIPPED according to existing delivery model
- stores provider message ID when available
- failure never rolls back task operation

Initial eligible notifications:

- task assigned
- task reassigned
- important status change
- due soon
- overdue
- relevant comment/mention if supported

Avoid spam.

============================================================
9. TELEGRAM TASK NOTIFICATION UX
============================================================

Example:

LINTEAM · Nueva tarea

Preparar informe de cobranzas

Prioridad: Alta
Vence: Hoy 17:00
Asignada por: José

[Ver tarea]
[Mis tareas]

Use Telegram inline keyboards where useful.

All web links must use:

https://linteam.online

============================================================
10. REACT — COMMUNICATION CHANNEL SETTINGS
============================================================

Implement visible UI inside authenticated LINTEAM.

Follow existing visual system.

Add an appropriate section such as:

Settings
→ Communication Channels

Telegram card:

TELEGRAM

Not connected

Receive task notifications and interact with LINTEAM from Telegram.

[Connect Telegram]

When clicked:

frontend calls authenticated link-token endpoint

backend returns safe deep link:

https://t.me/<bot_username>?start=<single_use_token>

Frontend opens/navigates to Telegram.

When connected:

TELEGRAM

Connected
@display_username

Notifications: ON/OFF

[Open Telegram]
[Disconnect]

Do NOT expose:
- bot token
- webhook secret
- permanent API keys

If username is unavailable, display "Connected" without inventing one.

============================================================
11. REACT — LINTEAM AGENT UI
============================================================

Implement a lightweight visible LINTEAM Agent interface.

DO NOT create a generic chatbot clone.

It should feel like an operational command surface.

Possible route:

/app/agent

Add to navigation only if appropriate to existing UX.

Suggested initial UI:

LINTEAM Agent

¿Qué necesita atención?

Quick actions:

[Mis tareas]
[Hoy]
[Atrasadas]
[Crear tarea]

Input:

"Escribí un comando..."

For Phase 01 this input maps to deterministic supported commands.

Examples:

/tasks
/today
/overdue
/task 154

If simple Spanish aliases are already supported, allow them.

Render results as useful task cards/actions, not fake AI prose.

Web UI must call the SAME LinteamAgentService through an authenticated backend
endpoint.

Do not duplicate task business logic in React.

============================================================
12. AGENT WEB ENDPOINT
============================================================

If not already implemented, expose an authenticated endpoint such as:

POST /api/v1/agent/execute

Request should be structured and validated.

Authenticated web user provides actor identity via existing auth.

Never allow frontend to choose arbitrary actor_user_id or organization_id.

Backend derives actor from auth/session/JWT.

Agent source:

WEB

Telegram source:

TELEGRAM

Both converge on LinteamAgentService.

============================================================
13. NOTIFICATION PREFERENCES
============================================================

Reuse existing preferences model if present.

Add Telegram preference only if not already implemented.

Desired behavior:

In-app: existing behavior
Email: existing/current
Telegram: enabled/disabled

Telegram notifications should default conservatively.

Connecting Telegram should NOT silently grant additional LINTEAM permissions.

Disconnecting Telegram should immediately prevent Telegram commands from
authenticating as that user.

============================================================
14. SECURITY TESTS — REQUIRED
============================================================

The previous implementation has insufficient coverage.

Add tests for:

LINKING
- token is single-use
- expired token rejected
- invalid token rejected
- token is not stored plaintext if current implementation hashes it
- Telegram username alone cannot authenticate
- duplicate Telegram user identity cannot link to multiple users unsafely
- disconnect invalidates identity

WEBHOOK
- missing secret rejected
- incorrect secret rejected
- correct secret accepted
- duplicate update_id processed once
- malformed update safe
- bot token never exposed

AUTHORIZATION
- Telegram user cannot access another organization's task
- employee cannot execute action outside RBAC
- manager/admin follows existing permissions
- callback cannot bypass permissions
- disconnected Telegram identity rejected

============================================================
15. AGENT OPERATION TESTS
============================================================

Test:

/tasks
/today
/overdue
/task

/done:
- asks confirmation
- confirm executes valid transition
- cancel does nothing
- duplicate confirmation idempotent
- invalid transition rejected safely

/comment:
- authorized comment works
- unauthorized comment rejected

/create:
- workflow starts
- structured state progresses
- cancel clears state
- expiration handled
- final confirmation required
- permission validated
- exactly one task created
- duplicate Telegram callback does not create duplicate task

============================================================
16. NOTIFICATION TESTS
============================================================

Test Telegram provider:

linked + enabled
→ delivery attempted

not linked
→ SKIPPED

preference disabled
→ SKIPPED

Telegram API failure
→ FAILED
→ task operation remains successful

successful delivery
→ SENT
→ provider message id stored if architecture supports it

No notification should cause task transaction rollback because Telegram is down.

============================================================
17. FRONTEND TESTS
============================================================

Using existing test infrastructure, cover:

- Telegram disconnected state
- Connect Telegram action
- connected state
- disconnect
- Telegram notification preference
- LINTEAM Agent route/component
- quick actions
- agent API success
- agent API error
- loading state

Do not introduce brittle pixel tests.

============================================================
18. USER EXPERIENCE
============================================================

Keep LINTEAM professional.

Do not make Telegram messages overly conversational.

Prefer:

LINTEAM · Tarea asignada

over:

"¡Hola! Soy tu asistente inteligente 🤖..."

No unnecessary emojis.

Agent UI should visually match LINTEAM.

============================================================
19. OBSERVABILITY
============================================================

Add structured logs where consistent with project conventions:

telegram.webhook.received
telegram.webhook.rejected
telegram.update.processed
telegram.delivery.sent
telegram.delivery.failed
agent.command.executed
agent.command.denied

Include correlation/update IDs.

Never log:
- bot token
- webhook secret
- raw link token
- unnecessary message content

============================================================
20. MIGRATION REVIEW
============================================================

Review the migration already created.

Confirm:

- additive
- correct down_revision
- single Alembic head
- indexes/unique constraints appropriate
- PostgreSQL compatible
- no destructive operations
- no secrets/default credentials

If /create workflow requires another table/column, prefer extending the current
uncommitted migration ONLY if it has never been deployed/pushed/shared and doing
so is safe in this working tree.

Otherwise create a new migration.

Explicitly report what you chose.

============================================================
21. BOTFATHER / PRODUCTION RUNBOOK
============================================================

Complete:

docs/TELEGRAM_AGENT_PHASE_01.md

Include exact manual steps for us AFTER code review.

BotFather:

- /newbot
- choose display name
- choose username
- obtain token
- optional command configuration

Suggested commands:

start - Vincular LINTEAM
help - Ver comandos
tasks - Mis tareas
today - Tareas de hoy
overdue - Tareas atrasadas
task - Ver tarea
create - Crear tarea
done - Completar tarea
comment - Comentar tarea
cancel - Cancelar operación

Production environment placeholders:

LINTEAM_TELEGRAM_ENABLED=true
LINTEAM_TELEGRAM_BOT_TOKEN=<secret>
LINTEAM_TELEGRAM_BOT_USERNAME=<username>
LINTEAM_TELEGRAM_WEBHOOK_SECRET=<random-secret>
LINTEAM_TELEGRAM_WEBHOOK_URL=https://linteam.online/api/v1/integrations/telegram/webhook

Document how to register webhook without leaking token into shell history where
possible.

Document webhook verification.

Document first account-link smoke test.

Do NOT execute production registration.

============================================================
22. VALIDATION
============================================================

Run targeted tests.

Then full relevant backend suite.

Then:

frontend tests
frontend build
typecheck/lint if configured
Alembic head validation
git diff --check

No long-running foreground production processes.

No production deploy.

============================================================
23. FINAL ACCEPTANCE TEST MATRIX
============================================================

Before declaring complete, verify logically/tests:

WEB:

Login
→ /app/agent
→ Mis tareas
→ receives authorized tasks

WEB:

Settings
→ Connect Telegram
→ receives deep link

TELEGRAM:

/start <token>
→ identity linked

TELEGRAM:

/tasks
→ authorized tasks returned

TELEGRAM:

/done <id>
→ confirmation
→ confirm
→ task completed
→ audit attributed to human

TELEGRAM:

/create
→ guided flow
→ confirmation
→ task created once
→ notification pipeline triggered

LINTEAM:

manager creates important task assigned to linked employee
→ work item succeeds
→ notification created
→ Telegram provider sends message

FAILURE:

Telegram API unavailable
→ task still succeeds
→ delivery FAILED
→ retry possible/future-compatible

============================================================
24. GIT SAFETY
============================================================

Do NOT automatically commit until all implementation/tests are complete.

At the end:

git status --short
git diff --stat
git diff --check

Explicitly identify unrelated dirty files.

Stage ONLY Phase 01 files.

If and only if implementation is complete and tests pass:

commit:

feat: add linteam agent with telegram integration

Before pushing, confirm the commit contains no:
- secrets
- .env
- linteam.db
- unrelated markdown
- unrelated local files

Normal push only.

NEVER force push.

If repository state makes safe commit impossible:
do not commit.
Report exactly why.

============================================================
DEFINITION OF DONE — PHASE 01
============================================================

Do NOT call this phase complete unless:

[ ] Telegram account can be securely linked
[ ] webhook verifies secret
[ ] webhook is idempotent
[ ] Telegram actually sends bot responses
[ ] /tasks works
[ ] /today works
[ ] /overdue works
[ ] /task works
[ ] /done works with confirmation
[ ] /comment works
[ ] /create works with controlled confirmation
[ ] Telegram task notifications actually use provider
[ ] provider failure does not break task mutation
[ ] Telegram settings UI exists
[ ] LINTEAM Agent web UI exists
[ ] web + Telegram use same agent application service
[ ] RBAC and organization boundaries tested
[ ] human attribution/audit tested
[ ] frontend builds
[ ] backend tests pass
[ ] migration chain valid
[ ] documentation/runbook complete
[ ] no secrets committed
[ ] no production deployment performed

Do not reduce scope by marking placeholders/TODOs as implementation.

If something cannot be safely completed, leave it explicitly incomplete and
report the blocker.

FINAL PRODUCT RULE:

We are building LINTEAM Agent, not a Telegram-specific task system.

Telegram is Channel Adapter #1.

LINTEAM remains the system of record.