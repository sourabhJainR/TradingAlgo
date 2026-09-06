from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from tradingalgo.core.domain import Bar, Order, OrderType, Side


@dataclass(frozen=True, slots=True)
class StrategyContext:
    cash: Decimal
    position_qty: Decimal


class Strategy(ABC):
    @abstractmethod
    def on_bar(self, bar: Bar, context: StrategyContext) -> Order | None:
        raise NotImplementedError


class MovingAverageCross(Strategy):
    """Small reference strategy; production strategies should add regime/risk filters."""

    def __init__(self, fast: int = 20, slow: int = 50) -> None:
        if fast >= slow or fast < 2:
            raise ValueError("fast must be >= 2 and smaller than slow")
        self.fast = fast
        self.slow = slow
        self._closes: list[Decimal] = []
        self._in_position = False

    def on_bar(self, bar: Bar, context: StrategyContext) -> Order | None:
        self._closes.append(bar.close)
        if len(self._closes) < self.slow:
            return None
        fast_ma = sum(self._closes[-self.fast:], Decimal("0")) / self.fast
        slow_ma = sum(self._closes[-self.slow:], Decimal("0")) / self.slow
        if fast_ma > slow_ma and not self._in_position:
            self._in_position = True
            return Order(bar.symbol, Side.BUY, Decimal("1"), OrderType.MARKET)
        if fast_ma < slow_ma and self._in_position:
            self._in_position = False
            return Order(bar.symbol, Side.SELL, Decimal("1"), OrderType.MARKET)
        return None
