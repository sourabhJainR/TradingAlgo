"""Compose heterogeneous evidence into transparent factor signals."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
from .models import Evidence, Horizon, Polarity, Signal

@dataclass(frozen=True)
class EvidenceBundle:
    ticker: str
    evidence: tuple[Evidence, ...]
    signals: tuple[Signal, ...]
    quality: float
    bullish: tuple[str, ...]
    bearish: tuple[str, ...]
    contradictions: tuple[str, ...]
    catalysts: tuple[str, ...]
    risks: tuple[str, ...]

def _age_factor(item: Evidence, now: datetime) -> float:
    age_hours = max(0.0, (now - item.observed_at.astimezone(timezone.utc)).total_seconds() / 3600)
    return max(0.0, 1.0 - age_hours / 720.0)

def _signed(item: Evidence, now: datetime) -> float:
    direction = {Polarity.BULLISH: 1.0, Polarity.BEARISH: -1.0}.get(item.polarity, 0.0)
    return direction * abs(item.severity) * item.confidence * _age_factor(item, now)

def compose_evidence(ticker: str, evidence: Iterable[Evidence], now: datetime | None = None) -> EvidenceBundle:
    now = now or datetime.now(timezone.utc)
    items = tuple(e for e in evidence if e.ticker.upper() == ticker.upper())
    groups: dict[str, list[Evidence]] = defaultdict(list)
    for item in items:
        groups[item.source_type.value].append(item)
    signals: list[Signal] = []
    for category, group in sorted(groups.items()):
        weighted = [_signed(e, now) for e in group]
        confidence = sum(e.confidence * _age_factor(e, now) for e in group) / len(group)
        score = max(-100.0, min(100.0, 100.0 * sum(weighted) / len(group)))
        signals.append(Signal(name=f"{category}_evidence", category=category, ticker=ticker.upper(), score=score,
            confidence=min(1.0, confidence), horizon=Horizon.MEDIUM,
            rationale=f"{len(group)} evidence item(s); weighted freshness/confidence score={score:.1f}",
            evidence_ids=[e.id for e in group]))
    bull = tuple(e.title for e in items if e.polarity is Polarity.BULLISH)
    bear = tuple(e.title for e in items if e.polarity is Polarity.BEARISH)
    contradictions = tuple(f"{b} vs {r}" for b in bull for r in bear)
    catalyst_tags = {"earnings", "guidance", "m_and_a", "contract_order", "product", "capital_return"}
    risk_tags = {"litigation", "regulatory", "geopolitical", "supply_chain", "financing"}
    catalysts = tuple(e.title for e in items if e.polarity is Polarity.BULLISH and catalyst_tags.intersection(e.tags))
    risks = tuple(e.title for e in items if e.polarity is Polarity.BEARISH and risk_tags.intersection(e.tags))
    source_coverage = min(1.0, len(groups) / 6.0)
    freshness = sum(_age_factor(e, now) for e in items) / len(items) if items else 0.0
    quality = 0.65 * source_coverage + 0.35 * freshness
    return EvidenceBundle(ticker=ticker.upper(), evidence=items, signals=tuple(signals), quality=quality,
        bullish=bull, bearish=bear, contradictions=contradictions, catalysts=catalysts, risks=risks)
