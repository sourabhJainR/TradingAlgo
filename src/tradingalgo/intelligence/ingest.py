from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable


@dataclass(frozen=True)
class Evidence:
    id: str
    source: str
    kind: str
    subject: str
    observed_at: datetime
    published_at: datetime | None
    payload: dict[str, Any]
    confidence: float = 1.0
    freshness_seconds: float | None = None

    @property
    def freshness(self) -> float:
        if self.freshness_seconds is None:
            return 1.0
        age_hours = max(self.freshness_seconds / 3600.0, 0.0)
        return max(0.05, 1.0 / (1.0 + age_hours / 24.0))


def make_evidence(
    source: str,
    kind: str,
    subject: str,
    payload: dict[str, Any],
    published_at: datetime | None = None,
    confidence: float = 1.0,
) -> Evidence:
    observed = datetime.now(timezone.utc)
    published = published_at.astimezone(timezone.utc) if published_at else None
    age = (observed - published).total_seconds() if published else None
    raw_id = f"{source}:{kind}:{subject}:{published.isoformat() if published else observed.isoformat()}"
    return Evidence(
        id=str(abs(hash(raw_id))),
        source=source,
        kind=kind,
        subject=subject,
        observed_at=observed,
        published_at=published,
        payload=payload,
        confidence=max(0.0, min(1.0, confidence)),
        freshness_seconds=age,
    )


def flatten_payload(response: Any) -> Iterable[dict[str, Any]]:
    payload = getattr(response, "payload", response)
    if isinstance(payload, list):
        yield from (x for x in payload if isinstance(x, dict))
    elif isinstance(payload, dict):
        yield payload
