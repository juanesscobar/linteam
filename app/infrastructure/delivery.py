from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class DeliveryMessage:
    channel: str
    recipient: str
    subject: str
    body: str


class DeliveryAdapter(Protocol):
    def send(self, message: DeliveryMessage) -> str: ...


class MockDeliveryAdapter:
    def send(self, message: DeliveryMessage) -> str:
        if not message.recipient or not message.body:
            raise ValueError("Recipient and body are required")
        return f"mock-{uuid4()}"


class ProviderNotConfigured(RuntimeError):
    pass
