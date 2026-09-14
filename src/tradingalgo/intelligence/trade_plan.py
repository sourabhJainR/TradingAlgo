"""Derive advisory entry, invalidation and target levels from market history.

These levels are deterministic research outputs, not brokerage orders or guarantees.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from ..data.providers import ProviderResponse
from ..technical.indicators import atr, technical_snapshot


@dataclass(frozen=True)
class TradePlan:
    ticker: str
    current_price: float
    buy_range_low: float
    buy_range_high: float
    stop_loss: float
    target_1: float
    target_2: float
    risk_per_share: float
    risk_reward_t1: float
    risk_reward_t2: float
    hypothesis: str
    prediction_basis: tuple[str, ...]
    invalidation: str
    technicals: dict[str, float]


def build_trade_plan(ticker: str, candles: pd.DataFrame, *, horizon: str = "medium") -> TradePlan:
    """Build a repeatable plan from OHLCV history without introducing predictions."""
    frame = _normalize_candles(candles)
    if len(frame) < 50:
        raise ValueError("at least 50 OHLCV rows are required for a trade plan")
    snapshot = technical_snapshot(frame)
    price = float(frame["close"].iloc[-1])
    atr_value = float(atr(frame["high"], frame["low"], frame["close"]).iloc[-1])
    sma20 = float(frame["close"].rolling(20).mean().iloc[-1])
    recent_low = float(frame["low"].tail(20).min())
    recent_high = float(frame["high"].tail(20).max())
    if not np.isfinite(atr_value) or atr_value <= 0:
        raise ValueError("ATR is unavailable for the supplied history")

    low = max(recent_low, min(price, sma20) - 0.5 * atr_value)
    high = min(price + 0.25 * atr_value, sma20 + 0.75 * atr_value)
    if high < low:
        low, high = min(price, sma20), max(price, sma20)
    stop = max(0.01, low - 1.5 * atr_value)
    risk = max(0.01, high - stop)
    target1 = high + risk
    target2 = high + 2.0 * risk

    basis = _basis(snapshot, price, sma20, recent_high, recent_low)
    direction = "bullish" if snapshot.get("price_vs_sma20_pct", 0.0) >= 0 else "recovery"
    hypothesis = (
        f"{ticker.upper()} has a {direction} setup if price holds the buy range and the supporting "
        f"technical signals remain intact over the {horizon} horizon."
    )
    invalidation = f"Invalidate the setup below {stop:.2f} or if the supporting trend evidence materially reverses."
    return TradePlan(
        ticker=ticker.upper(), current_price=price,
        buy_range_low=round(low, 4), buy_range_high=round(high, 4),
        stop_loss=round(stop, 4), target_1=round(target1, 4), target_2=round(target2, 4),
        risk_per_share=round(risk, 4),
        risk_reward_t1=round((target1 - high) / risk, 2),
        risk_reward_t2=round((target2 - high) / risk, 2),
        hypothesis=hypothesis, prediction_basis=tuple(basis),
        invalidation=invalidation, technicals=snapshot,
    )


def candles_from_provider(response: ProviderResponse) -> pd.DataFrame:
    """Normalize Twelve Data or Alpha Vantage time-series payloads to OHLCV."""
    payload = response.payload
    rows: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        values = payload.get("values")
        if isinstance(values, list):
            rows = [row for row in values if isinstance(row, dict)]
        else:
            for key, value in payload.items():
                if isinstance(value, dict) and str(key).lower().startswith("time series"):
                    rows = [dict(row, datetime=date) for date, row in value.items() if isinstance(row, dict)]
                    break
    elif isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    if not rows:
        raise ValueError("provider response contains no OHLCV rows")
    frame = pd.DataFrame(rows)
    rename = {str(column).lower().replace(" ", "_"): str(column).lower().replace(" ", "_") for column in frame.columns}
    frame = frame.rename(columns=rename)
    aliases = {
        "datetime": "date", "date": "date", "timestamp": "date",
        "open": "open", "1._open": "open", "high": "high", "2._high": "high",
        "low": "low", "3._low": "low", "close": "close", "4._close": "close",
        "volume": "volume", "5._volume": "volume",
    }
    frame = frame.rename(columns={column: aliases[column] for column in frame.columns if column in aliases})
    if "date" in frame.columns:
        frame = frame.set_index("date")
    return _normalize_candles(frame)


def _normalize_candles(candles: pd.DataFrame) -> pd.DataFrame:
    frame = candles.copy()
    frame.columns = [str(column).lower().strip().replace(" ", "_") for column in frame.columns]
    required = {"open", "high", "low", "close", "volume"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing OHLCV columns: {sorted(missing)}")
    for column in required:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=list(required)).sort_index()


def _basis(snapshot: dict[str, float], price: float, sma20: float, recent_high: float, recent_low: float) -> list[str]:
    basis = [f"price={price:.2f}", f"SMA20={sma20:.2f}", f"20-day range={recent_low:.2f}-{recent_high:.2f}"]
    if "rsi14" in snapshot:
        basis.append(f"RSI14={snapshot['rsi14']:.1f}")
    if "macd_histogram" in snapshot:
        basis.append(f"MACD histogram={snapshot['macd_histogram']:.4f}")
    if "volume_ratio20" in snapshot:
        basis.append(f"volume/20-day average={snapshot['volume_ratio20']:.2f}x")
    return basis
