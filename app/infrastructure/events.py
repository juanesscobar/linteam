import json
import logging
from typing import Protocol
from uuid import UUID


class EventPublisher(Protocol):
    def publish(self, event_id: UUID, event_type: str, payload: dict[str, object]) -> None: ...


class LoggingEventPublisher:
    """Reliable local transport sink; replaceable by a broker adapter."""

    def __init__(self) -> None:
        self.logger = logging.getLogger("linteam.events")

    def publish(self, event_id: UUID, event_type: str, payload: dict[str, object]) -> None:
        self.logger.info(
            json.dumps(
                {
                    "event": "domain_event_published",
                    "event_id": str(event_id),
                    "event_type": event_type,
                    "payload_keys": sorted(payload),
                }
            )
        )
