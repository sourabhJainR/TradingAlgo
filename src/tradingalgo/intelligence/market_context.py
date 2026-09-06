from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class MarketContext:
    index_vs_200dma_pct: float
    breadth_pct: float
    volatility_z: float
    sector_relative_strength: float
    macro_bias: float


def market_context(index_close: float, index_sma200: float | None,
                   advancing: int, declining: int, volatility_z: float,
                   sector_return: float, market_return: float, macro_bias: float = 0.0) -> MarketContext:
    index_vs_200 = ((index_close / index_sma200) - 1.0) * 100 if index_sma200 else 0.0
    total = advancing + declining
    breadth = 100.0 * advancing / total if total else 50.0
    relative = sector_return - market_return
    return MarketContext(index_vs_200, breadth, volatility_z, relative, max(-1.0, min(1.0, macro_bias)))


def sector_signal(relative_strength: float) -> float:
    return max(-100.0, min(100.0, relative_strength * 20.0))
