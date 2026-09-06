from __future__ import annotations

from .models import Horizon, Signal
from .technical import TechnicalSnapshot


def build_technical_signal(ticker: str, snapshot: TechnicalSnapshot) -> Signal:
    """Turn the deterministic technical snapshot into an explainable signal."""
    score = 0.0
    reasons: list[str] = []
    if snapshot.sma20 is not None:
        score += 15 if snapshot.close > snapshot.sma20 else -15
        reasons.append("above SMA20" if snapshot.close > snapshot.sma20 else "below SMA20")
    if snapshot.sma50 is not None:
        score += 20 if snapshot.close > snapshot.sma50 else -20
        reasons.append("above SMA50" if snapshot.close > snapshot.sma50 else "below SMA50")
    if snapshot.sma200 is not None:
        score += 30 if snapshot.close > snapshot.sma200 else -30
        reasons.append("above SMA200" if snapshot.close > snapshot.sma200 else "below SMA200")
    if snapshot.rsi14 is not None:
        if 50 <= snapshot.rsi14 <= 70:
            score += 15
            reasons.append("RSI confirms positive momentum")
        elif snapshot.rsi14 < 35:
            score += 5
            reasons.append("RSI is oversold")
        elif snapshot.rsi14 > 75:
            score -= 10
            reasons.append("RSI is overbought")
    if snapshot.momentum20 is not None:
        score += 20 if snapshot.momentum20 > 0 else -20
        reasons.append("positive 20-day momentum" if snapshot.momentum20 > 0 else "negative 20-day momentum")
    score = max(-100.0, min(100.0, score))
    polarity = "bullish" if score > 10 else "bearish" if score < -10 else "neutral"
    confidence = min(0.95, 0.35 + 0.12 * len(reasons))
    return Signal(
        name="technical_trend",
        category="technical",
        ticker=ticker.upper(),
        score=score,
        confidence=confidence,
        horizon=Horizon.SWING,
        rationale=f"Technical structure is {polarity}: " + "; ".join(reasons),
        evidence_ids=[],
        features={
            "trend_score": snapshot.trend_score,
            "rsi14": snapshot.rsi14 or 0.0,
            "momentum20": snapshot.momentum20 or 0.0,
            "volatility20": snapshot.volatility20 or 0.0,
        },
    )
