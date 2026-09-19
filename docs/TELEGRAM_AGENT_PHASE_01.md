# LINTEAM Agent — Telegram Phase 01

Telegram is an adapter for LINTEAM; it is not a separate task system. All task
operations are authorized as the linked LINTEAM user and recorded in LINTEAM audit.

## Production setup

1. Create a bot with BotFather and record its username and token in the production
   secret manager (never in Git).
2. Generate a random webhook secret and configure `LINTEAM_TELEGRAM_ENABLED=true`,
   `LINTEAM_TELEGRAM_BOT_TOKEN`, `LINTEAM_TELEGRAM_BOT_USERNAME`,
   `LINTEAM_TELEGRAM_WEBHOOK_SECRET`, and `LINTEAM_TELEGRAM_WEBHOOK_URL`.
3. Register `https://linteam.online/api/v1/integrations/telegram/webhook` with
   Telegram `setWebhook`, passing the same secret token.
4. Verify a rejected request without the `X-Telegram-Bot-Api-Secret-Token` header,
   then send `/start` from the bot.
5. From authenticated LINTEAM, create a one-time Connect Telegram link. It expires
   after ten minutes and is stored only as a hash.
6. Smoke-test `/tasks`, `/today`, `/overdue`, `/task <id>`, and `/done <id>`.

`/done` requires an expiring confirmation. Telegram `update_id` values are persisted
to make webhook retries harmless. Bot delivery is intentionally not enabled until the
production delivery worker is configured; webhook processing never exposes its token.

## Deferred

Phase 02 may add an LLM intent resolver that only produces validated proposals.
Future adapters are Email, WhatsApp, Slack, Teams and Conciencia. None may access
the LINTEAM database directly.
