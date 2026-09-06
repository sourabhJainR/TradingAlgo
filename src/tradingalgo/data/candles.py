from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class Candle:
    ticker: str
    session: date
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


def alpha_vantage_daily(ticker: str, payload: dict[str, Any]) -> list[Candle]:
    series = payload.get("Time Series (Daily)", {})
    candles: list[Candle] = []
    for day, row in series.items():
        try:
            candles.append(Candle(ticker, date.fromisoformat(day), float(row["1. open"]), float(row["2. high"]), float(row["3. low"]), float(row["4. close"]), float(row.get("5. volume", 0))))
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(candles, key=lambda x: x.session)


def finnhub_candles(ticker: str, payload: dict[str, Any]) -> list[Candle]:
    if payload.get("s") not in (None, "ok"):
        return []
    timestamps = payload.get("t", [])
    opens, highs, lows, closes, volumes = (payload.get(k, []) for k in ("o", "h", "l", "c", "v"))
    candles: list[Candle] = []
    for values in zip(timestamps, opens, highs, lows, closes, volumes, strict=False):
        try:
            ts, op, hi, lo, cl, vol = values
            candles.append(Candle(ticker, date.fromtimestamp(int(ts)), float(op), float(hi), float(lo), float(cl), float(vol)))
        except (TypeError, ValueError, OverflowError):
            continue
    return sorted(candles, key=lambda x: x.session)
