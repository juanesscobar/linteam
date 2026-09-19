"""Small Telegram Bot API adapter; credentials stay exclusively in Settings."""

import logging
from typing import Any

import httpx

from app.settings import Settings

logger = logging.getLogger("linteam.telegram")


class TelegramBotClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        if not settings.telegram_enabled or not settings.telegram_bot_token:
            raise RuntimeError("Telegram delivery is not configured")
        self._base_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
        self._transport = transport

    async def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10, transport=self._transport) as client:
                response = await client.post(f"{self._base_url}/{method}", json=payload)
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "telegram.delivery.failed method=%s error=%s", method, type(exc).__name__
            )
            raise RuntimeError("Telegram API request failed") from exc
        if not body.get("ok"):
            logger.warning("telegram.delivery.failed method=%s status=api_error", method)
            raise RuntimeError("Telegram API rejected request")
        return body["result"]

    async def send_message(
        self, chat_id: str, text: str, reply_markup: dict[str, Any] | None = None
    ) -> str:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return str((await self._post("sendMessage", payload))["message_id"])

    async def answer_callback_query(self, callback_query_id: str, text: str = "") -> None:
        await self._post(
            "answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text}
        )

    async def edit_message_text(self, chat_id: str, message_id: int, text: str) -> None:
        await self._post(
            "editMessageText", {"chat_id": chat_id, "message_id": message_id, "text": text}
        )
