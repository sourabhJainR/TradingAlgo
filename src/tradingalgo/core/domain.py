from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from uuid import uuid4


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class OrderStatus(str, Enum):
    CREATED = "created"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class Bar:
    symbol: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True, slots=True)
class Quote:
    symbol: str
    timestamp: datetime
    bid: Decimal
    ask: Decimal
    bid_size: Decimal = Decimal("0")
    ask_size: Decimal = Decimal("0")

    @property
    def mid(self) -> Decimal:
        return (self.bid + self.ask) / Decimal("2")

    @property
    def spread(self) -> Decimal:
        return max(Decimal("0"), self.ask - self.bid)


@dataclass(frozen=True, slots=True)
class Order:
    symbol: str
    side: Side
    quantity: Decimal
    order_type: OrderType = OrderType.MARKET
    limit_price: Decimal | None = None
    client_order_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("Order quantity must be positive")
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("Limit orders require limit_price")


@dataclass(frozen=True, slots=True)
class Fill:
    order_id: str
    symbol: str
    side: Side
    quantity: Decimal
    price: Decimal
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class Position:
    symbol: str
    quantity: Decimal = Decimal("0")
    average_price: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")

    def apply_fill(self, fill: Fill) -> None:
        signed_qty = fill.quantity if fill.side == Side.BUY else -fill.quantity
        if self.quantity == 0 or (self.quantity > 0 and signed_qty > 0) or (self.quantity < 0 and signed_qty < 0):
            new_qty = self.quantity + signed_qty
            if new_qty != 0:
                self.average_price = ((abs(self.quantity) * self.average_price) + (abs(signed_qty) * fill.price)) / abs(new_qty)
            self.quantity = new_qty
            return

        closing_qty = min(abs(self.quantity), abs(signed_qty))
        pnl_per_share = fill.price - self.average_price
        if self.quantity < 0:
            pnl_per_share = self.average_price - fill.price
        self.realized_pnl += closing_qty * pnl_per_share
        self.quantity += signed_qty
        if self.quantity == 0:
            self.average_price = Decimal("0")
        elif abs(signed_qty) > closing_qty:
            self.average_price = fill.price
