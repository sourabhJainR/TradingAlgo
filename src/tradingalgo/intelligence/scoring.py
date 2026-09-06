"""Transparent multi-signal fusion for investment advisories."""
from __future__ import annotations

from collections.abc import Iterable

from tradingalgo.intelligence.models import Advisory, Evidence, Horizon, Signal


CATEGORY_WEIGHTS = {
    "technical": 0.16,
    "fundamental": 0.20,
    "valuation": 0.12,
    "analyst": 0.08,
    "sentiment": 0.08,
    "sector": 0.08,
    "event": 0.10,
    "geopolitical": 0.06,
    "legal": 0.05,
    "macro": 0.07,
}


def _clamp(value: float, low: float = -100.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def evidence_score(evidence: Evidence) -> float:
    polarity = {"bullish": 1.0, "bearish": -1.0, "neutral": 0.0, "mixed": 0.0}[evidence.polarity.value]
    return _clamp(100 * polarity * evidence.severity * evidence.confidence * evidence.novelty * evidence.freshness)


def fuse_signals(signals: Iterable[Signal], evidence: Iterable[Evidence], ticker: str, horizon: Horizon) -> Advisory:
    signal_list = list(signals)
    evidence_list = list(evidence)
    weighted_total = 0.0
    total_weight = 0.0
    for signal in signal_list:
        weight = CATEGORY_WEIGHTS.get(signal.category, 0.05) * signal.confidence
        weighted_total += signal.score * weight
        total_weight += weight
    score = _clamp(weighted_total / total_weight) if total_weight else 0.0

    bullish = [s.rationale for s in signal_list if s.score >= 20]
    bearish = [s.rationale for s in signal_list if s.score <= -20]
    contradictions = []
    if bullish and bearish:
        contradictions.append("Bullish and bearish evidence are both material; conviction is reduced.")

    quality = sum(e.confidence * e.freshness for e in evidence_list) / len(evidence_list) if evidence_list else 0.0
    confidence = min(1.0, quality * (0.55 + min(0.45, len(signal_list) / 12)))
    action = "STRONG BUY" if score >= 55 and confidence >= 0.65 else "BUY" if score >= 25 else "AVOID" if score <= -45 else "WATCH" if score < 10 else "HOLD"

    return Advisory(
        ticker=ticker,
        action=action,
        score=score,
        confidence=confidence,
        horizon=horizon,
        bull_case=bullish,
        bear_case=bearish,
        contradictions=contradictions,
        risks=bearish,
        catalysts=bullish,
        signals=signal_list,
        data_quality=quality,
    )
