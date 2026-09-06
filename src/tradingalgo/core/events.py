from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Event:
    name: str
    timestamp: datetime
    payload: object


Handler = Callable[[Event], None]


class EventBus:
    """Small synchronous event bus; deterministic and easy to replace with a durable bus later."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}
        self.history: list[Event] = []

    def subscribe(self, name: str, handler: Handler) -> None:
        self._handlers.setdefault(name, []).append(handler)

    def publish(self, name: str, payload: object, timestamp: datetime | None = None) -> Event:
        event = Event(name, timestamp or datetime.now(timezone.utc), payload)
        self.history.append(event)
        for handler in tuple(self._handlers.get(name, [])):
            handler(event)
        return event
