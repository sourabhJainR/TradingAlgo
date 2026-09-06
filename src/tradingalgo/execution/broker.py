from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from datetime import datetime, timezone

from tradingalgo.core.domain import Fill, Order, OrderStatus, Side


class Broker(ABC):
    @abstractmethod
    def submit(self, order: Order, market_price: Decimal) -> tuple[OrderStatus, Fill | None]:
        raise NotImplementedError

    @abstractmethod
    def cancel(self, client_order_id: str) -> bool:
        raise NotImplementedError


class PaperBroker(Broker):
    """Deterministic broker for paper trading and tests.

    A real broker adapter must never bypass the same risk/execution gateway.
    """

    def __init__(self) -> None:
        self.orders: dict[str, Order] = {}
        self.fills: list[Fill] = []

    def submit(self, order: Order, market_price: Decimal) -> tuple[OrderStatus, Fill | None]:
        if market_price <= 0:
            return OrderStatus.REJECTED, None
        self.orders[order.client_order_id] = order
        fill = Fill(
            order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=market_price,
            timestamp=datetime.now(timezone.utc),
        )
        self.fills.append(fill)
        return OrderStatus.FILLED, fill

    def cancel(self, client_order_id: str) -> bool:
        return self.orders.pop(client_order_id, None) is not None
