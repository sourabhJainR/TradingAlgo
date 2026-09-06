"""Transparent multi-factor advisory decision engine."""
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict
from .models import Advisory, Evidence, Horizon, Signal, Polarity
from .scoring import CATEGORY_WEIGHTS

@dataclass(frozen=True)
class DecisionConfig:
    min_confidence: float = 0.55
    strong_buy_score: float = 55.0
    buy_score: float = 25.0
    avoid_score: float = -45.0


def _signed(e: Evidence) -> float:
    direction = {Polarity.BULLISH: 1.0, Polarity.BEARISH: -1.0}.get(e.polarity, 0.0)
    return 100.0 * direction * abs(e.severity) * e.confidence * e.novelty * e.freshness


def evidence_signals(ticker: str, evidence: list[Evidence]) -> list[Signal]:
    groups: dict[str, list[Evidence]] = defaultdict(list)
    for item in evidence:
        if item.ticker.upper() == ticker.upper():
            groups[item.source_type.value].append(item)
    result: list[Signal] = []
    for category, items in groups.items():
        values = [_signed(item) for item in items]
        score = max(-100.0, min(100.0, sum(values) / len(values)))
        confidence = sum(item.confidence * item.freshness for item in items) / len(items)
        result.append(Signal(name=f"{category}_factor", category=category, ticker=ticker.upper(), score=score,
            confidence=min(1.0, confidence), horizon=Horizon.MEDIUM,
            rationale=f"{len(items)} {category} evidence item(s), freshness/confidence adjusted score {score:.1f}.",
            evidence_ids=[item.id for item in items]))
    return result


def decide(ticker: str, signals: list[Signal], evidence: list[Evidence], horizon: Horizon = Horizon.MEDIUM, config: DecisionConfig | None = None) -> Advisory:
    config = config or DecisionConfig()
    weighted = 0.0
    weights = 0.0
    for signal in signals:
        weight = CATEGORY_WEIGHTS.get(signal.category, 0.05) * signal.confidence
        weighted += signal.score * weight
        weights += weight
    score = max(-100.0, min(100.0, weighted / weights if weights else 0.0))
    bull = [s.rationale for s in signals if s.score >= 20]
    bear = [s.rationale for s in signals if s.score <= -20]
    categories = {s.category for s in signals}
    coverage = min(1.0, len(categories) / 8.0)
    freshness = sum(e.freshness * e.confidence for e in evidence) / len(evidence) if evidence else 0.0
    contradiction_penalty = 0.10 if bull and bear else 0.0
    confidence = max(0.0, min(1.0, (0.60 * freshness + 0.40 * coverage) * (1.0 - contradiction_penalty)))
    if confidence < config.min_confidence:
        action = "WATCH"
    elif score >= config.strong_buy_score:
        action = "STRONG BUY"
    elif score >= config.buy_score:
        action = "BUY"
    elif score <= config.avoid_score:
        action = "AVOID"
    elif score < 10:
        action = "WATCH"
    else:
        action = "HOLD"
    contradictions = ["Material bullish and bearish factors coexist; conviction reduced."] if bull and bear else []
    risks = [s.rationale for s in signals if s.category in {"legal", "geopolitical", "macro"} and s.score < -10]
    catalysts = [s.rationale for s in signals if s.category in {"event", "analyst", "sector", "fundamental"} and s.score > 10]
    return Advisory(ticker=ticker.upper(), action=action, score=score, confidence=confidence, horizon=horizon,
        bull_case=bull, bear_case=bear, contradictions=contradictions, risks=risks, catalysts=catalysts,
        signals=signals, data_quality=freshness * coverage)
