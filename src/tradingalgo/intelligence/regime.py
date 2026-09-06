"""Market and sector regime context used as a top-down modifier."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Regime:
    market: str
    sector: str
    breadth: float
    volatility: float
    risk_score: float


def classify_regime(*, index_vs_200dma_pct: float, breadth_pct: float, volatility_z: float) -> Regime:
    """Classify the backdrop without making a stock-level prediction."""
    if index_vs_200dma_pct > 3 and breadth_pct > 60 and volatility_z < 1:
        market = "risk_on"
    elif index_vs_200dma_pct < -3 or breadth_pct < 35 or volatility_z > 2:
        market = "risk_off"
    else:
        market = "mixed"
    risk_score = max(-100.0, min(100.0, breadth_pct - 50 - volatility_z * 15 + index_vs_200dma_pct * 3))
    return Regime(market=market, sector="unknown", breadth=breadth_pct, volatility=volatility_z, risk_score=risk_score)
