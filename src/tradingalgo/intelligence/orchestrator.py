"""End-to-end provider orchestration with fallback, exposure and persistence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Any

from ..data.health import ProviderHealthRegistry
from ..data.providers import ProviderResponse
from .evidence_store import deduplicate
from .exposure import ExposureMap
from .models import Evidence, Signal
from .pipeline import normalize_provider_payloads
from .evidence_composer import EvidenceBundle, compose_evidence
from .persistent_store import SQLiteEvidenceStore


@dataclass(frozen=True)
class FetchCandidate:
    provider: str
    fetch: Callable[[], ProviderResponse]


@dataclass(frozen=True)
class OrchestrationResult:
    ticker: str
    evidence: tuple[Evidence, ...]
    signals: tuple[Signal, ...]
    bundle: EvidenceBundle
    provider_errors: dict[str, str]
    selected_providers: dict[str, str]


class IntelligenceOrchestrator:
    """Coordinate independent channels; one failed provider never blocks the run."""
    def __init__(self, health: ProviderHealthRegistry | None = None, store: SQLiteEvidenceStore | None = None) -> None:
        self.health = health or ProviderHealthRegistry()
        self.store = store

    def _first_available(self, channel: str, candidates: list[FetchCandidate], errors: dict[str, str]) -> tuple[str, ProviderResponse] | None:
        for candidate in candidates:
            status = self.health.get(candidate.provider)
            if not status.available:
                errors[candidate.provider] = "provider health gate is open"
                continue
            try:
                response = candidate.fetch()
                self.health.record_success(candidate.provider)
                return candidate.provider, response
            except Exception as exc:
                self.health.record_failure(candidate.provider)
                errors[f"{channel}:{candidate.provider}"] = str(exc)
        return None

    def collect(
        self,
        ticker: str,
        *,
        quote: list[FetchCandidate] | None = None,
        analyst: list[FetchCandidate] | None = None,
        news: list[FetchCandidate] | None = None,
        sec: list[FetchCandidate] | None = None,
        fred: list[FetchCandidate] | None = None,
        events: list[FetchCandidate] | None = None,
        exposure: ExposureMap | None = None,
    ) -> OrchestrationResult:
        errors: dict[str, str] = {}
        selected: dict[str, str] = {}
        payloads: dict[str, Any] = {}
        channels = (("quote", quote), ("analyst", analyst), ("news", news), ("sec", sec), ("fred", fred), ("events", events))
        for channel, candidates in channels:
            if not candidates:
                continue
            result = self._first_available(channel, candidates, errors)
            if result is None:
                continue
            provider, response = result
            selected[channel] = provider
            if channel == "quote":
                key = provider
            elif channel == "sec":
                key = "sec_edgar_companyfacts"
            elif channel == "fred":
                key = "fred"
            else:
                key = f"{provider}_{channel}"
            payload = response.payload
            if channel == "fred" and isinstance(payload, dict):
                payload = dict(payload)
            payloads[key] = payload

        normalized = normalize_provider_payloads(ticker, payloads)
        errors.update(normalized.provider_errors)
        evidence = deduplicate(normalized.evidence)
        if exposure:
            evidence = exposure.enrich_many(evidence)
        if self.store:
            self.store.upsert_many(evidence)
        bundle = compose_evidence(ticker, evidence)
        return OrchestrationResult(
            ticker=ticker.upper(), evidence=tuple(evidence), signals=bundle.signals,
            bundle=bundle, provider_errors=errors, selected_providers=selected,
        )


def evidence_age_seconds(evidence: Evidence) -> float:
    return max(0.0, (datetime.now(timezone.utc) - evidence.observed_at).total_seconds())
