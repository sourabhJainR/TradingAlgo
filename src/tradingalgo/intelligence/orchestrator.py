"""End-to-end provider orchestration, history, exposure and advisory scoring."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Any
from ..data.health import ProviderHealthRegistry
from ..data.providers import ProviderResponse
from .evidence_store import deduplicate
from .exposure import ExposureMap
from .models import Evidence, Signal, Advisory, Horizon, SourceType
from .pipeline import normalize_provider_payloads
from .evidence_composer import EvidenceBundle, compose_evidence
from .persistent_store import SQLiteEvidenceStore
from .fundamentals import normalize_companyfacts
from .macro import normalize_fred, macro_evidence
from .event_exposure import event_to_evidence
from .decision_engine import decide, evidence_signals

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
    advisory: Advisory
    provider_errors: dict[str, str]
    selected_providers: dict[str, str]

class IntelligenceOrchestrator:
    def __init__(self, health: ProviderHealthRegistry | None = None, store: SQLiteEvidenceStore | None = None) -> None:
        self.health = health or ProviderHealthRegistry()
        self.store = store

    def _first_available(self, channel: str, candidates: list[FetchCandidate], errors: dict[str, str]):
        for candidate in candidates:
            if not self.health.get(candidate.provider).available:
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

    def collect(self, ticker: str, *, quote: list[FetchCandidate] | None = None,
                analyst: list[FetchCandidate] | None = None, news: list[FetchCandidate] | None = None,
                sec: list[FetchCandidate] | None = None, fred: list[FetchCandidate] | None = None,
                events: list[FetchCandidate] | None = None, exposure: ExposureMap | None = None,
                horizon: Horizon = Horizon.MEDIUM) -> OrchestrationResult:
        errors: dict[str, str] = {}; selected: dict[str, str] = {}; payloads: dict[str, Any] = {}; evidence: list[Evidence] = []
        for channel, candidates in (("quote", quote), ("analyst", analyst), ("news", news), ("sec", sec), ("fred", fred), ("events", events)):
            if not candidates: continue
            result = self._first_available(channel, candidates, errors)
            if result is None: continue
            provider, response = result; selected[channel] = provider
            if channel == "quote": key = provider
            elif channel == "sec": key = "sec_edgar_companyfacts"
            elif channel == "fred": key = "fred"
            else: key = f"{provider}_{channel}"
            payloads[key] = response.payload

        normalized = normalize_provider_payloads(ticker, payloads)
        errors.update(normalized.provider_errors); evidence.extend(normalized.evidence)

        sec_payload = payloads.get("sec_edgar_companyfacts")
        if isinstance(sec_payload, dict):
            try:
                for fact in normalize_companyfacts(ticker, sec_payload):
                    filed = None
                    if fact.filing_date:
                        try: filed = datetime.fromisoformat(fact.filing_date).replace(tzinfo=timezone.utc)
                        except ValueError: pass
                    evidence.append(Evidence(id=f"sec:{fact.accession or fact.concept}:{fact.period_end}", ticker=ticker.upper(), source_type=SourceType.SEC_FILING,
                        source_name=selected.get("sec", "sec_edgar"), observed_at=filed or datetime.now(timezone.utc), published_at=filed,
                        title=f"SEC {fact.concept}", summary=f"{fact.concept}={fact.value} {fact.unit} for {fact.period_end}",
                        confidence=.9, novelty=.6, facts={"concept":fact.concept,"value":fact.value,"unit":fact.unit,"period_end":fact.period_end}))
            except (TypeError, ValueError, KeyError) as exc: errors["sec:normalize"] = str(exc)

        fred_payload = payloads.get("fred")
        if isinstance(fred_payload, dict):
            try:
                observations = normalize_fred(str(fred_payload.get("series_id") or fred_payload.get("id") or "unknown"), fred_payload)
                for observation in observations[-5:]: evidence.append(macro_evidence(ticker, observation))
            except (TypeError, ValueError, KeyError) as exc: errors["fred:normalize"] = str(exc)

        for item in evidence:
            if exposure: pass
        event_payload = payloads.get(f"{selected.get('events')}_events") if selected.get("events") else None
        if isinstance(event_payload, list):
            for row in event_payload:
                if isinstance(row, dict):
                    title = str(row.get("headline") or row.get("title") or "Event")
                    text = str(row.get("summary") or row.get("description") or row.get("text") or "")
                    source = str(row.get("source") or selected.get("events") or "event")
                    evidence.extend(exposure.propagate_event(ticker, title, text, source) if exposure else [event_to_evidence(ticker, title, text, source)])

        if exposure: evidence = exposure.enrich_many(evidence)
        evidence = deduplicate(evidence)
        if self.store: self.store.upsert_many(evidence)
        bundle = compose_evidence(ticker, evidence)
        signals = evidence_signals(ticker, evidence)
        advisory = decide(ticker, signals, evidence, horizon)
        return OrchestrationResult(ticker=ticker.upper(), evidence=tuple(evidence), signals=tuple(signals), bundle=bundle,
            advisory=advisory, provider_errors=errors, selected_providers=selected)

def evidence_age_seconds(evidence: Evidence) -> float:
    return max(0.0, (datetime.now(timezone.utc) - evidence.observed_at).total_seconds())
