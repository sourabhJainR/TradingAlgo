from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Iterable

from .ingest import Evidence


class Polarity(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class Signal:
    factor: str
    polarity: Polarity
    strength: float
    confidence: float
    horizon: str
    evidence_ids: tuple[str, ...] = ()

    @property
    def signed_score(self) -> float:
        sign = 1.0 if self.polarity is Polarity.BULLISH else -1.0 if self.polarity is Polarity.BEARISH else 0.0
        return sign * self.strength * self.confidence


@dataclass
class Advisory:
    symbol: str
    score: float
    confidence: float
    rating: str
    bull_case: list[str] = field(default_factory=list)
    bear_case: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)


def fuse(symbol: str, signals: Iterable[Signal]) -> Advisory:
    items = list(signals)
    if not items:
        return Advisory(symbol, 0.0, 0.0, "WATCH")
    score = sum(s.signed_score for s in items) / len(items)
    confidence = sum(s.confidence for s in items) / len(items)
    bull = [s.factor for s in items if s.polarity is Polarity.BULLISH]
    bear = [s.factor for s in items if s.polarity is Polarity.BEARISH]
    contradictions = [f"{b} vs {r}" for b in bull for r in bear]
    if score >= 0.45 and confidence >= 0.65:
        rating = "STRONG BUY"
    elif score >= 0.15:
        rating = "BUY"
    elif score <= -0.45 and confidence >= 0.65:
        rating = "STRONG AVOID"
    elif score <= -0.15:
        rating = "AVOID"
    else:
        rating = "WATCH"
    return Advisory(symbol, score, confidence, rating, bull, bear, contradictions, items)


def event_signal(event: Evidence, polarity: Polarity, strength: float, horizon: str = "swing") -> Signal:
    return Signal(
        factor=f"{event.kind}:{event.subject}",
        polarity=polarity,
        strength=max(0.0, min(1.0, strength)),
        confidence=event.confidence * event.freshness,
        horizon=horizon,
        evidence_ids=(event.id,),
    )
