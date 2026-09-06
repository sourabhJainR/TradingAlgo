"""Compose heterogeneous evidence into a transparent advisory."""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .models import Advisory, Evidence, Horizon, Signal, SourceType


def _source_score(items: list[Evidence]) -> tuple[float, float]:
    if not items:
        return 0.0, 0.0
    weighted = 0.0
    weight = 0.0
    for item in items:
        freshness = item.freshness
        w = max(0.05, item.confidence * (0.5 + 0.5 * freshness))
        weighted += item.severity * 100.0 * w
        weight += w
    return (weighted / weight if weight else 0.0, min(1.0, weight / 3.0))


def evidence_signals(evidence: Iterable[Evidence]) -> list[Signal]:
    groups: dict[SourceType, list[Evidence]] = defaultdict(list)
    for item in evidence:
        groups[item.source_type].append(item)
    signals: list[Signal] = []
    for source_type, items in groups.items():
        score, confidence = _source_score(items)
        if not items:
            continue
        horizon = max(items, key=lambda x: x.confidence).horizon
        signals.append(
            Signal(
                name=f"{source_type.value}_evidence",
                category=source_type.value,
                ticker=items[0].ticker,
                score=max(-100.0, min(100.0, score)),
                confidence=confidence,
                horizon=horizon,
                rationale=f"{len(items)} {source_type.value} evidence item(s) fused with freshness and confidence weighting.",
                evidence_ids=[x.id for x in items],
            )
        )
    return signals


def compose_advisory(
    ticker: str, evidence: Iterable[Evidence], technical_signal: Signal | None = None
) -> Advisory:
    items = [x for x in evidence if x.ticker.upper() == ticker.upper()]
    signals = evidence_signals(items)
    if technical_signal is not None:
        signals.append(technical_signal)
    if not signals:
        return Advisory(ticker=ticker.upper(), action="WATCH", score=0.0, confidence=0.0, horizon=Horizon.MEDIUM)

    weights = [max(0.05, s.confidence) for s in signals]
    score = sum(s.score * w for s, w in zip(signals, weights)) / sum(weights)
    confidence = min(1.0, sum(weights) / (len(weights) * 1.25))
    bullish = [s for s in signals if s.score > 10]
    bearish = [s for s in signals if s.score < -10]
    contradictions = [f"{b.category} vs {r.category}" for b in bullish for r in bearish]

    action = "WATCH"
    if score >= 35 and confidence >= 0.65:
        action = "STRONG BUY"
    elif score >= 12:
        action = "BUY"
    elif score <= -35 and confidence >= 0.65:
        action = "STRONG AVOID"
    elif score <= -12:
        action = "AVOID"

    risks = [x.summary for x in items if x.polarity.value == "bearish" and x.source_type in {SourceType.LEGAL, SourceType.REGULATORY}]
    catalysts = [x.summary for x in items if x.polarity.value == "bullish" and x.source_type in {SourceType.NEWS, SourceType.M_AND_A, SourceType.FUNDAMENTAL}]
    source_types = {x.source_type for x in items}
    data_quality = min(1.0, 0.35 * len(source_types) + 0.1 * sum(x.confidence for x in items) / max(1, len(items)))
    horizon = max(signals, key=lambda s: s.confidence).horizon

    return Advisory(
        ticker=ticker.upper(), action=action, score=max(-100.0, min(100.0, score)), confidence=confidence,
        horizon=horizon, bull_case=[s.rationale for s in bullish], bear_case=[s.rationale for s in bearish],
        contradictions=contradictions[:12], risks=risks[:8], catalysts=catalysts[:8], signals=signals,
        data_quality=data_quality,
    )
