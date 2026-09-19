Continue from the CURRENT LINTEAM working tree.

Do NOT restart, revert, reset, stash, clean, checkout, or rewrite the existing
LINTEAM Agent implementation.

CURRENT VERIFIED STATE

Already implemented:

- LinteamAgentService
- deterministic commands:
  /tasks
  /today
  /overdue
  /task
  /done with confirmation
  /comment
- secure Telegram identity linking
- hashed single-use expiring link tokens
- Telegram webhook secret validation
- Telegram update_id idempotency
- human actor audit attribution
- additive Alembic migration
- Telegram environment configuration
- TelegramBotClient using httpx:
  - send_message
  - callback support
  - edit_message_text
- webhook -> LinteamAgentService -> Telegram outbound response
- Telegram delivery failure does NOT rollback the LINTEAM operation
- 14 backend tests passing
- one Alembic head
- git diff --check passing
- no production deploy
- no commit yet

PHASE 01 IS NOT COMPLETE.

The remaining work is known.

DO NOT stop after implementing only one remaining item.

Complete ALL remaining Phase 01 requirements in this run unless there is a real
technical blocker.

============================================================
1. COMPLETE /create
============================================================

Implement the controlled Telegram task creation workflow.

Required UX:

/create

→ ask title
→ choose assignee
→ choose due date
→ choose priority
→ show final confirmation
→ create only after confirmation

Reuse existing LINTEAM:
- user/employee model
- organization boundaries
- priority enum
- WorkItem creation application service
- RBAC
- audit
- notification pipeline

DO NOT create WorkItem directly from Telegram adapter.

Use persisted short-lived structured workflow state if necessary.

Required:

/cancel

must cancel and clear pending workflow.

Suggested flow:

User:
/create

Bot:
Título de la nueva tarea:

User:
Preparar informe de cobranzas

Bot:
Asignar a:

[María]
[Pedro]
[Yo]

Bot:
Vencimiento:

[Hoy]
[Mañana]
[Sin fecha]

Bot:
Prioridad:

[Baja]
[Normal]
[Alta]
[Urgente]

Bot:

Nueva tarea

Preparar informe de cobranzas

Responsable: María
Vence: Mañana
Prioridad: Alta

[Crear tarea]
[Cancelar]

Only confirmation may execute creation.

Repeated Telegram callback MUST NOT create a second task.

If current LINTEAM priority model differs, reuse the actual model.

If user list is large, implement safe pagination or a reasonable selection
strategy rather than dumping all employees.

============================================================
2. COMPLETE TELEGRAM NOTIFICATION PROVIDER
============================================================

Inspect and EXTEND the notification architecture already present.

Do NOT build a second notification system.

Implement:

TelegramNotificationProvider

using the TelegramBotClient already created.

Flow:

WorkItem event
      ↓
NotificationService
      ↓
TelegramNotificationProvider
      ↓
verified Telegram identity
      ↓
TelegramBotClient
      ↓
user

Initial Telegram notification events:

- task assigned
- task reassigned
- important status change
- due soon
- overdue
- relevant comment/mention if supported by current domain

Respect:

- Telegram globally enabled
- verified communication identity
- identity enabled
- user Telegram notification preference

Delivery results must use the existing delivery model:

SENT
FAILED
SKIPPED

or equivalent current enums.

Telegram failure MUST NEVER rollback:
- task creation
- task update
- status transition
- comment

Store provider message ID if supported.

Example:

LINTEAM · Nueva tarea

Preparar informe de cobranzas

Prioridad: Alta
Vence: Hoy 17:00
Asignada por: José

[Ver tarea]
[Mis tareas]

Use:

https://linteam.online

============================================================
3. COMPLETE TELEGRAM SETTINGS UI
============================================================

Implement the visible authenticated React UI.

Use the current LINTEAM design system.

Add an appropriate section:

Settings
→ Communication Channels

Telegram disconnected:

Telegram

Conectá Telegram para recibir notificaciones y gestionar tus tareas desde el
bot de LINTEAM.

[Conectar Telegram]

Click:

→ authenticated backend generates one-use link token
→ backend returns safe Telegram deep link
→ frontend opens:

https://t.me/<bot_username>?start=<token>

Connected state:

Telegram
Conectado
@username     (only if actually available)

Notificaciones Telegram: ON/OFF

[Abrir Telegram]
[Desconectar]

Requirements:

- loading states
- error states
- confirmation for disconnect if appropriate
- no secrets exposed
- bot token never reaches browser
- webhook secret never reaches browser

============================================================
4. COMPLETE LINTEAM AGENT WEB UI
============================================================

Implement a visible operational Agent interface.

Do NOT make a ChatGPT clone.

Suggested route:

/app/agent

Add navigation entry where appropriate.

UI:

LINTEAM Agent

¿Qué necesita atención?

[Mis tareas]
[Hoy]
[Atrasadas]
[Crear tarea]

Command input below.

Quick actions should execute through the SAME LinteamAgentService used by
Telegram.

Web request:

React
→ authenticated agent API
→ LinteamAgentService
→ existing application services

The frontend must NOT reproduce business logic.

For Phase 01, deterministic commands are enough.

Support:

/tasks
/today
/overdue
/task <id>

and existing safe write operations where appropriate.

For "Crear tarea", either:
- reuse existing LINTEAM create-task modal, preferably
OR
- call the same controlled agent create capability

Do NOT create another independent task form if an existing reusable component
already exists.

Render useful task results/cards/actions instead of fake conversational prose.

============================================================
5. FINISH CALLBACK CONFIRMATION
============================================================

Verify /done end-to-end:

/done <id>

→ task loaded
→ permission checked
→ confirmation keyboard
→ Confirmar
→ permission checked again
→ valid workflow transition
→ application service
→ audit
→ edit/send Telegram result

Cancel must perform no mutation.

Repeated confirmation must be idempotent.

Callback payload must not be trusted as authorization.

============================================================
6. COMPLETE SECURITY TEST MATRIX
============================================================

14 tests are not sufficient for this feature.

Add focused tests for the actual attack/failure boundaries.

LINKING

- valid token links account
- expired token rejected
- invalid token rejected
- consumed token rejected
- plaintext token is not persisted
- Telegram username cannot authenticate user
- duplicate Telegram numeric ID cannot bind unsafely
- disconnected identity cannot authenticate

WEBHOOK

- missing secret rejected
- wrong secret rejected
- valid secret accepted
- duplicate update_id processed once
- malformed update handled safely
- Telegram failure does not corrupt operation

RBAC

- employee cannot access unauthorized task
- cross-organization access rejected
- callback cannot bypass authorization
- /create assignee scope validated
- disconnected Telegram identity rejected

============================================================
7. COMPLETE COMMAND TEST MATRIX
============================================================

Tests required:

/tasks
/today
/overdue
/task

/done:
- confirmation generated
- cancel does nothing
- confirm executes exactly once
- duplicate callback idempotent
- invalid transition rejected

/comment:
- authorized works
- unauthorized rejected

/create:
- workflow starts
- title captured
- assignee validated
- due date captured
- priority validated
- confirmation required
- cancel clears workflow
- expired workflow rejected/cleared
- creation occurs exactly once
- duplicate callback does not duplicate task
- audit attributed to human actor

============================================================
8. COMPLETE TELEGRAM PROVIDER TESTS
============================================================

Test:

linked + enabled
→ Telegram delivery attempted

not linked
→ SKIPPED

Telegram preference disabled
→ SKIPPED

Telegram API success
→ SENT

Telegram API failure
→ FAILED

provider message id stored if supported

MOST IMPORTANT:

Telegram failure
→ WorkItem operation still succeeds

============================================================
9. FRONTEND TESTS
============================================================

Using the existing frontend testing stack, add practical tests for:

Telegram settings:
- disconnected
- connect
- connected
- notification toggle
- disconnect
- loading/error state

Agent:
- route renders
- quick actions
- authorized result rendering
- loading state
- backend error state

Do not add brittle visual pixel tests.

============================================================
10. REVIEW MIGRATION
============================================================

Review the existing uncommitted migration.

If /create workflow state requires schema changes, decide whether to extend the
existing migration or create another migration.

Because nothing has been committed/deployed yet, extending the current migration
may be acceptable ONLY if it is clearly safe.

Report the decision.

Ensure:

alembic heads

returns exactly one head.

No destructive migration.

============================================================
11. DOCUMENTATION
============================================================

Finish:

docs/TELEGRAM_AGENT_PHASE_01.md

It must contain a real production runbook.

Include:

BOTFATHER

/newbot

Suggested commands:

start - Vincular cuenta LINTEAM
help - Ver comandos
tasks - Mis tareas
today - Tareas de hoy
overdue - Tareas atrasadas
task - Ver tarea
create - Crear tarea
done - Completar tarea
comment - Comentar tarea
cancel - Cancelar operación

Required production environment variables.

Expected webhook:

https://linteam.online/api/v1/integrations/telegram/webhook

Explain:

- creating bot
- setting commands
- generating webhook secret
- adding variables to Dokploy
- deploying migration
- registering webhook
- verifying webhook
- linking first account
- smoke testing
- rollback considerations

DO NOT perform production setup.

============================================================
12. FULL VALIDATION
============================================================

After implementation:

Run targeted tests first.

Then full relevant backend tests.

Then:

- frontend tests
- frontend build
- frontend typecheck/lint if configured
- Alembic head validation
- git diff --check

Do not run blocking production servers.

Do not deploy.

============================================================
13. DO NOT STOP EARLY
============================================================

Do NOT stop after:

- implementing /create only
- implementing notification provider only
- implementing UI only
- adding several tests only

Continue until all remaining Phase 01 areas above are implemented and validated.

Only stop early if there is a REAL technical blocker.

If blocked:

1. identify exact blocker
2. show affected file/code
3. explain why proceeding would be unsafe
4. leave other independent requirements completed

============================================================
14. FINAL DEFINITION OF DONE
============================================================

Before reporting completion verify:

[ ] /tasks works through Telegram
[ ] /today works through Telegram
[ ] /overdue works through Telegram
[ ] /task works through Telegram
[ ] /done confirmation works
[ ] /comment works
[ ] /create guided workflow works
[ ] /cancel works
[ ] Telegram outbound replies work
[ ] Telegram notification provider exists
[ ] notification delivery state is persisted
[ ] Telegram outage does not break task mutation
[ ] secure Telegram account linking works
[ ] webhook authentication works
[ ] webhook idempotency works
[ ] callback idempotency works
[ ] Telegram Settings React UI exists
[ ] Telegram connect/disconnect works
[ ] Telegram notification preference exists
[ ] /app/agent or equivalent exists
[ ] web Agent uses same LinteamAgentService
[ ] RBAC tests exist
[ ] cross-org tests exist
[ ] linking security tests exist
[ ] /create tests exist
[ ] notification failure tests exist
[ ] frontend tests pass
[ ] frontend production build passes
[ ] backend tests pass
[ ] one Alembic head
[ ] git diff --check passes
[ ] documentation/runbook complete
[ ] no secrets committed
[ ] production was NOT deployed

Only after ALL applicable boxes are satisfied may you describe Phase 01 as
complete.

============================================================
15. GIT
============================================================

At the very end:

git status --short
git diff --stat
git diff --check

Identify unrelated dirty files explicitly.

Do NOT stage unrelated files.

If Phase 01 is complete and safe to isolate, stage only LINTEAM Agent Phase 01
files and create:

feat: add linteam agent with telegram integration

Before commit inspect staged diff.

Do NOT push if doing so could include unrelated work.

Never force push.

If safe normal push is possible after validation, report what would be pushed
before doing it unless current repository instructions explicitly authorize
normal pushes.

No production deployment.

FINAL RULE:

Do not return another progress checkpoint merely because one additional component
was implemented.

Finish LINTEAM Agent Phase 01 end-to-end.