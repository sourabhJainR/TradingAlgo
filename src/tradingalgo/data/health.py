from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ProviderHealth:
    provider: str
    successes: int = 0
    failures: int = 0
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    consecutive_failures: int = 0

    @property
    def success_rate(self) -> float:
        total = self.successes + self.failures
        return self.successes / total if total else 0.0

    @property
    def available(self) -> bool:
        return self.consecutive_failures < 3

    def record_success(self) -> None:
        self.successes += 1
        self.consecutive_failures = 0
        self.last_success_at = datetime.now(timezone.utc)

    def record_failure(self) -> None:
        self.failures += 1
        self.consecutive_failures += 1
        self.last_failure_at = datetime.now(timezone.utc)


class ProviderHealthRegistry:
    def __init__(self) -> None:
        self._items: dict[str, ProviderHealth] = {}

    def get(self, provider: str) -> ProviderHealth:
        if provider not in self._items:
            self._items[provider] = ProviderHealth(provider=provider)
        return self._items[provider]

    def record_success(self, provider: str) -> None:
        self.get(provider).record_success()

    def record_failure(self, provider: str) -> None:
        self.get(provider).record_failure()

    def snapshot(self) -> dict[str, ProviderHealth]:
        return dict(self._items)
