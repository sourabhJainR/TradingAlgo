from __future__ import annotations
from dataclasses import dataclass
from math import sqrt
from typing import Sequence

@dataclass(frozen=True)
class TechnicalSnapshot:
    close: float
    sma20: float | None
    sma50: float | None
    sma200: float | None
    rsi14: float | None
    volatility20: float | None
    momentum20: float | None
    trend_score: float


def _sma(values: Sequence[float], n: int) -> float | None:
    return sum(values[-n:]) / n if len(values) >= n else None


def _rsi(values: Sequence[float], n: int = 14) -> float | None:
    if len(values) <= n: return None
    gains = [max(0.0, values[i] - values[i-1]) for i in range(len(values)-n, len(values))]
    losses = [max(0.0, values[i-1] - values[i]) for i in range(len(values)-n, len(values))]
    avg_loss = sum(losses) / n
    if avg_loss == 0: return 100.0
    return 100.0 - 100.0 / (1.0 + (sum(gains) / n) / avg_loss)


def snapshot(closes: Sequence[float]) -> TechnicalSnapshot:
    if not closes: raise ValueError('closes cannot be empty')
    close = float(closes[-1])
    sma20, sma50, sma200 = _sma(closes,20), _sma(closes,50), _sma(closes,200)
    rsi = _rsi(closes)
    momentum = (close / closes[-21] - 1.0) if len(closes) >= 21 and closes[-21] else None
    returns = [closes[i]/closes[i-1]-1 for i in range(max(1,len(closes)-20),len(closes)) if closes[i-1]]
    vol = sqrt(sum((x-sum(returns)/len(returns))**2 for x in returns)/len(returns))*sqrt(252) if returns else None
    parts = []
    if sma20: parts.append(1 if close>sma20 else -1)
    if sma50: parts.append(1 if close>sma50 else -1)
    if sma200: parts.append(1 if close>sma200 else -1)
    if rsi is not None: parts.append(1 if 50<rsi<70 else -1 if rsi<35 or rsi>75 else 0)
    trend = sum(parts)/len(parts) if parts else 0.0
    return TechnicalSnapshot(close,sma20,sma50,sma200,rsi,vol,momentum,trend)
