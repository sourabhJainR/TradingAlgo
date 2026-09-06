from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from tradingalgo.core.domain import Order, Side


@dataclass(frozen=True, slots=True)
class RiskLimits:
    max_order_notional: Decimal = Decimal("5000")
    max_position_notional: Decimal = Decimal("20000")
    max_daily_loss: Decimal = Decimal("500")
    max_open_orders: int = 10
    max_price_age_seconds: int = 10


@dataclass(frozen=True, slots=True)
class RiskDecision:
    approved: bool
    reason: str = "approved"


class RiskEngine:
    def __init__(self, limits: RiskLimits) -> None:
        self.limits = limits
        self.kill_switch = False

    def evaluate(
        self,
        order: Order,
        reference_price: Decimal,
        current_position_qty: Decimal,
        realized_pnl_today: Decimal,
        open_order_count: int,
    ) -> RiskDecision:
        if self.kill_switch:
            return RiskDecision(False, "kill switch is active")
        if reference_price <= 0:
            return RiskDecision(False, "invalid reference price")
        notional = order.quantity * reference_price
        if notional > self.limits.max_order_notional:
            return RiskDecision(False, "order exceeds max order notional")
        signed_qty = order.quantity if order.side == Side.BUY else -order.quantity
        projected = abs(current_position_qty + signed_qty) * reference_price
        if projected > self.limits.max_position_notional:
            return RiskDecision(False, "projected position exceeds max notional")
        if realized_pnl_today <= -self.limits.max_daily_loss:
            return RiskDecision(False, "daily loss limit reached")
        if open_order_count >= self.limits.max_open_orders:
            return RiskDecision(False, "too many open orders")
        return RiskDecision(True)
