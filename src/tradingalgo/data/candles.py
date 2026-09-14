from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
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


def nse_historical(ticker: str, payload: dict[str, Any]) -> list[Candle]:
    """Normalize the public NSE historical equity response."""
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    candles: list[Candle] = []
    for row in rows:
        try:
            raw_date = str(row.get("mTIMESTAMP") or row.get("CH_TIMESTAMP") or row.get("TIMESTAMP"))
            session = datetime.strptime(raw_date[:10], "%d-%b-%Y").date()
            candles.append(Candle(
                ticker,
                session,
                float(row["CH_OPENING_PRICE"]),
                float(row["CH_TRADE_HIGH_PRICE"]),
                float(row["CH_TRADE_LOW_PRICE"]),
                float(row["CH_CLOSING_PRICE"]),
                float(row.get("CH_TOT_TRADED_QTY", 0)),
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(candles, key=lambda x: x.session)
