"""Dependency-light technical indicators for advisory research.

Inputs are expected to be ordered oldest -> newest. These indicators are
signals, not predictions, and should be combined with fundamental and event
context before an advisory is produced.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window, min_periods=window).mean()


def ema(close: pd.Series, window: int) -> pd.Series:
    return close.ewm(span=window, adjust=False, min_periods=window).mean()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / window, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / window, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    signal_line = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "signal": signal_line, "histogram": line - signal_line})


def bollinger(close: pd.Series, window: int = 20, deviations: float = 2.0) -> pd.DataFrame:
    mid = sma(close, window)
    std = close.rolling(window, min_periods=window).std()
    return pd.DataFrame({"mid": mid, "upper": mid + deviations * std, "lower": mid - deviations * std})


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    previous = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous).abs(), (low - previous).abs()], axis=1
    ).max(axis=1)
    return true_range.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()


def technical_snapshot(frame: pd.DataFrame) -> dict[str, float]:
    required = {"high", "low", "close", "volume"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing OHLCV columns: {sorted(missing)}")
    close = frame["close"]
    macd_frame = macd(close)
    bb = bollinger(close)
    latest = frame.iloc[-1]
    price = float(latest["close"])
    values = {
        "price_vs_sma20_pct": float((price / sma(close, 20).iloc[-1] - 1) * 100),
        "price_vs_sma50_pct": float((price / sma(close, 50).iloc[-1] - 1) * 100),
        "price_vs_sma200_pct": float((price / sma(close, 200).iloc[-1] - 1) * 100),
        "rsi14": float(rsi(close).iloc[-1]),
        "macd_histogram": float(macd_frame["histogram"].iloc[-1]),
        "bollinger_position": float(
            (price - bb["lower"].iloc[-1]) / (bb["upper"].iloc[-1] - bb["lower"].iloc[-1])
        ),
        "volume_ratio20": float(latest["volume"] / frame["volume"].rolling(20).mean().iloc[-1]),
    }
    return {key: value for key, value in values.items() if np.isfinite(value)}
