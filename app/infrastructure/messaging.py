from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NormalizedInboundMessage:
    event_id: str
    external_user_id: str
    text: str
    channel: str


class InvalidProviderPayload(ValueError):
    pass


def normalize_message(channel: str, payload: dict[str, object]) -> NormalizedInboundMessage:
    try:
        if channel == "telegram":
            message = payload["message"]  # type: ignore[index]
            sender = message["from"]  # type: ignore[index]
            return NormalizedInboundMessage(
                event_id=str(payload["update_id"]),
                external_user_id=str(sender["id"]),  # type: ignore[index]
                text=str(message.get("text", "")),  # type: ignore[union-attr]
                channel=channel,
            )
        if channel == "whatsapp":
            value = payload["entry"][0]["changes"][0]["value"]  # type: ignore[index]
            message = value["messages"][0]
            return NormalizedInboundMessage(
                event_id=str(message["id"]),
                external_user_id=str(message["from"]),
                text=str(message.get("text", {}).get("body", "")),
                channel=channel,
            )
        if channel == "email":
            return NormalizedInboundMessage(
                event_id=str(payload["message_id"]),
                external_user_id=str(payload["from"]),
                text=str(payload.get("text", "")),
                channel=channel,
            )
    except (KeyError, IndexError, TypeError) as exc:
        raise InvalidProviderPayload(f"Invalid {channel} payload") from exc
    raise InvalidProviderPayload("Unsupported channel")
