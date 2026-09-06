"""End-to-end provider orchestration, evidence history, exposure and advisory scoring."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

from ..data.candles import Candle
from ..data.health import ProviderHealthRegistry
from ..data.providers import ProviderResponse
from .analytics_history import AnalyticalHistory
from .decision_engine import decide, evidence_signals
from .evidence_composer import EvidenceBundle, compose_evidence
from .evidence_store import deduplicate
from .event_exposure import event_to_evidence
from .exposure import ExposureMap
from .factor_engine import build_fundamental_factors, build_valuation_signal
from .learning import LearningStore, PredictionSnapshot, prediction_id_for
from .models import Advisory, Evidence, Horizon, Signal
from .outcomes import PriceOutcome, realize_price_outcome
from .persistent_store import SQLiteEvidenceStore
from .pipeline import normalize_provider_payloads

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
    prediction: PredictionSnapshot

class IntelligenceOrchestrator:
    def __init__(self, health: ProviderHealthRegistry | None = None, store: SQLiteEvidenceStore | None = None,
                 history: AnalyticalHistory | None = None, learning: LearningStore | None = None) -> None:
        self.health = health or ProviderHealthRegistry(); self.store = store; self.history = history; self.learning = learning

    def _first_available(self, channel: str, candidates: list[FetchCandidate], errors: dict[str, str]):
        for candidate in candidates:
            if not self.health.get(candidate.provider).available:
                errors[candidate.provider] = "provider health gate is open"; continue
            try:
                response = candidate.fetch(); self.health.record_success(candidate.provider); return candidate.provider, response
            except Exception as exc:
                self.health.record_failure(candidate.provider); errors[f"{channel}:{candidate.provider}"] = str(exc)
        return None

    def collect(self, ticker: str, *, quote: list[FetchCandidate] | None = None, analyst: list[FetchCandidate] | None = None,
                news: list[FetchCandidate] | None = None, sec: list[FetchCandidate] | None = None,
                fred: list[FetchCandidate] | None = None, events: list[FetchCandidate] | None = None,
                exposure: ExposureMap | None = None, horizon: Horizon = Horizon.MEDIUM,
                as_of: datetime | None = None) -> OrchestrationResult:
        errors: dict[str, str] = {}; selected: dict[str, str] = {}; payloads: dict[str, Any] = {}; evidence: list[Evidence] = []
        for channel, candidates in (("quote", quote), ("analyst", analyst), ("news", news), ("sec", sec), ("fred", fred), ("events", events)):
            if not candidates: continue
            result = self._first_available(channel, candidates, errors)
            if result is None: continue
            provider, response = result; selected[channel] = provider
            key = provider if channel == "quote" else ("sec_edgar_companyfacts" if channel == "sec" else "fred" if channel == "fred" else f"{provider}_{channel}")
            payloads[key] = response.payload
        normalized = normalize_provider_payloads(ticker, payloads); errors.update(normalized.provider_errors); evidence.extend(normalized.evidence)
        event_payload = payloads.get(f"{selected.get('events')}_events") if selected.get("events") else None; rows: list[dict[str, Any]] = []
        if isinstance(event_payload, list): rows = [r for r in event_payload if isinstance(r, dict)]
        elif isinstance(event_payload, dict):
            candidate_rows = event_payload.get("events") or event_payload.get("data") or event_payload.get("results")
            if isinstance(candidate_rows, list): rows = [r for r in candidate_rows if isinstance(r, dict)]
        for row in rows:
            title = str(row.get("headline") or row.get("title") or "Event"); text = str(row.get("summary") or row.get("description") or row.get("text") or "")
            source = str(row.get("source") or selected.get("events") or "event"); url = row.get("url") or row.get("source_url")
            evidence.extend(exposure.propagate_event(ticker, title, text, source, url) if exposure else [event_to_evidence(ticker, title, text, source, url)])
        if exposure: evidence = exposure.enrich_many(evidence)
        evidence = deduplicate(evidence)
        if self.store: self.store.upsert_many(evidence)
        if self.history: self.history.upsert(evidence)
        point_in_time = as_of or datetime.now(timezone.utc)
        signals = evidence_signals(ticker, evidence); signals.extend(build_fundamental_factors(ticker, evidence, as_of=point_in_time, horizon=horizon))
        valuation = build_valuation_signal(ticker, evidence, as_of=point_in_time, horizon=horizon)
        if valuation: signals.append(valuation)
        bundle = compose_evidence(ticker, evidence); advisory = decide(ticker, signals, evidence, horizon)
        prediction = PredictionSnapshot.from_advisory(advisory, point_in_time, prediction_id_for(advisory, point_in_time))
        if self.learning: self.learning.save_prediction(prediction)
        return OrchestrationResult(ticker=ticker.upper(), evidence=tuple(evidence), signals=tuple(signals), bundle=bundle,
            advisory=advisory, provider_errors=errors, selected_providers=selected, prediction=prediction)

    def realize_prediction(self, prediction: PredictionSnapshot, candles: Sequence[Candle],
                           benchmark_candles: Sequence[Candle] | None = None) -> PriceOutcome:
        outcome = realize_price_outcome(prediction, candles, benchmark_candles)
        if self.learning: self.learning.save_outcome(outcome.observation)
        return outcome

    def realize_advisory(self, result: OrchestrationResult, candles: Sequence[Candle],
                         benchmark_candles: Sequence[Candle] | None = None) -> PriceOutcome:
        return self.realize_prediction(result.prediction, candles, benchmark_candles)

def evidence_age_seconds(evidence: Evidence) -> float:
    return max(0.0, (datetime.now(timezone.utc) - evidence.observed_at).total_seconds())
