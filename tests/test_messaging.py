import pytest

from app.infrastructure.messaging import InvalidProviderPayload, normalize_message


def test_normalizes_whatsapp_message() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"id": "wamid.1", "from": "5951", "text": {"body": "Comprar tinta"}}
                            ]
                        }
                    }
                ]
            }
        ]
    }
    message = normalize_message("whatsapp", payload)
    assert (message.event_id, message.external_user_id, message.text) == (
        "wamid.1",
        "5951",
        "Comprar tinta",
    )


def test_normalizes_email_and_rejects_invalid_payload() -> None:
    message = normalize_message(
        "email", {"message_id": "mail-1", "from": "person@example.com", "text": "Ayuda"}
    )
    assert message.channel == "email"
    with pytest.raises(InvalidProviderPayload):
        normalize_message("telegram", {"update_id": 1})
