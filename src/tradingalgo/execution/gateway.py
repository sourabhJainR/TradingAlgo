from __future__ import annotations

from decimal import Decimal

from tradingalgo.core.domain import Fill, Order, OrderStatus
from tradingalgo.execution.broker import Broker
from tradingalgo.risk.engine import RiskEngine


class ExecutionGateway:
    """Single path from strategy intent to broker.

    This boundary is deliberately strict: strategy code cannot call a broker directly.
    """

    def __init__(self, broker: Broker, risk: RiskEngine) -> None:
        self.broker = broker
        self.risk = risk
        self._seen_orders: set[str] = set()
        self.realized_pnl_today = Decimal("0")
        self.open_order_count = 0

    def submit(self, order: Order, reference_price: Decimal, current_position_qty: Decimal) -> tuple[OrderStatus, Fill | None, str]:
        if order.client_order_id in self._seen_orders:
            return OrderStatus.REJECTED, None, "duplicate client order id"
        decision = self.risk.evaluate(
            order,
            reference_price,
            current_position_qty,
            self.realized_pnl_today,
            self.open_order_count,
        )
        if not decision.approved:
            return OrderStatus.REJECTED, None, decision.reason
        self._seen_orders.add(order.client_order_id)
        status, fill = self.broker.submit(order, reference_price)
        if status == OrderStatus.FILLED and fill is not None:
            self.realized_pnl_today = self.realized_pnl_today
        return status, fill, "approved"
