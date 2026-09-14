from __future__ import annotations

from math import sqrt
from statistics import mean, pstdev
from typing import Any, Sequence


def _closes(candles: Sequence[Any]) -> list[float]:
    return [float(item.close) for item in candles if getattr(item, "close", None) is not None]


def _highs(candles: Sequence[Any]) -> list[float]:
    return [float(item.high) for item in candles if getattr(item, "high", None) is not None]


def _lows(candles: Sequence[Any]) -> list[float]:
    return [float(item.low) for item in candles if getattr(item, "low", None) is not None]


def _sma(values: Sequence[float], period: int) -> float | None:
    if not values:
        return None
    window = values[-period:]
    return mean(window)


def _ema(values: Sequence[float], period: int) -> float | None:
    if not values:
        return None
    alpha = 2.0 / (period + 1.0)
    value = values[0]
    for item in values[1:]:
        value = alpha * item + (1.0 - alpha) * value
    return value


def _rsi(closes: Sequence[float], period: int = 14) -> float | None:
    if len(closes) <= period:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(closes[-period - 1 : -1], closes[-period:], strict=True):
        change = current - previous
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    average_gain = mean(gains)
    average_loss = mean(losses)
    if average_loss == 0:
        return 100.0 if average_gain else 50.0
    return 100.0 - (100.0 / (1.0 + average_gain / average_loss))


def _atr(candles: Sequence[Any], period: int = 14) -> float | None:
    if not candles:
        return None
    rows = list(candles[-period - 1 :])
    ranges: list[float] = []
    previous_close: float | None = None
    for item in rows:
        high = float(item.high)
        low = float(item.low)
        if previous_close is None:
            ranges.append(high - low)
        else:
            ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
        previous_close = float(item.close)
    return mean(ranges[-period:]) if ranges else None


def _max_drawdown(closes: Sequence[float]) -> float:
    peak = closes[0]
    worst = 0.0
    for price in closes:
        peak = max(peak, price)
        if peak:
            worst = min(worst, (price / peak - 1.0) * 100.0)
    return worst


def _annualized_volatility(closes: Sequence[float]) -> float | None:
    if len(closes) < 3:
        return None
    returns = [current / previous - 1.0 for previous, current in zip(closes[:-1], closes[1:], strict=True) if previous]
    return pstdev(returns) * sqrt(252.0) * 100.0 if len(returns) > 1 else None


def analyze(candles: Sequence[Any]) -> dict[str, float | str | None]:
    closes = _closes(candles)
    highs = _highs(candles)
    lows = _lows(candles)
    if not closes:
        return {}
    price = closes[-1]
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd = ema12 - ema26 if ema12 is not None and ema26 is not None else None
    signal_values = []
    for index in range(max(0, len(closes) - 60), len(closes)):
        fast = _ema(closes[: index + 1], 12)
        slow = _ema(closes[: index + 1], 26)
        if fast is not None and slow is not None:
            signal_values.append(fast - slow)
    macd_signal = _ema(signal_values, 9) if signal_values else None
    std20 = pstdev(closes[-20:]) if len(closes) >= 2 else 0.0
    sma20 = _sma(closes, 20)
    upper = sma20 + 2.0 * std20 if sma20 is not None else None
    lower = sma20 - 2.0 * std20 if sma20 is not None else None
    atr14 = _atr(candles, 14)
    rsi14 = _rsi(closes, 14)
    high20 = max(highs[-20:]) if highs else price
    low20 = min(lows[-20:]) if lows else price
    high52 = max(highs[-252:]) if highs else price
    low52 = min(lows[-252:]) if lows else price
    return {
        "rsi14": round(rsi14, 2) if rsi14 is not None else None,
        "macd": round(macd, 4) if macd is not None else None,
        "macd_signal": round(macd_signal, 4) if macd_signal is not None else None,
        "macd_histogram": round(macd - macd_signal, 4) if macd is not None and macd_signal is not None else None,
        "bollinger_upper": round(upper, 2) if upper is not None else None,
        "bollinger_lower": round(lower, 2) if lower is not None else None,
        "atr14": round(atr14, 2) if atr14 is not None else None,
        "volatility_annualized_pct": round(_annualized_volatility(closes), 2) if _annualized_volatility(closes) is not None else None,
        "max_drawdown_pct": round(_max_drawdown(closes), 2),
        "distance_from_52w_high_pct": round((price / high52 - 1.0) * 100.0, 2) if high52 else None,
        "distance_from_52w_low_pct": round((price / low52 - 1.0) * 100.0, 2) if low52 else None,
        "breakout_20d": "yes" if price >= high20 * 0.995 else "no",
        "oversold": "yes" if rsi14 is not None and rsi14 < 30 else "no",
        "overbought": "yes" if rsi14 is not None and rsi14 > 70 else "no",
    }


def position_size(
    capital: float,
    risk_percent: float,
    entry: float,
    stop: float,
    max_position_percent: float = 25.0,
) -> dict[str, float]:
    if capital <= 0 or risk_percent <= 0 or entry <= 0 or stop <= 0:
        raise ValueError("capital, risk_percent, entry and stop must be positive")
    if stop >= entry:
        raise ValueError("stop must be below entry for a long-position risk calculation")
    if not 0 < max_position_percent <= 100:
        raise ValueError("max_position_percent must be between 0 and 100")
    risk_budget = capital * risk_percent / 100.0
    risk_per_share = entry - stop
    units_by_risk = risk_budget / risk_per_share
    max_position_value = capital * max_position_percent / 100.0
    units_by_cap = max_position_value / entry
    units = max(0.0, min(units_by_risk, units_by_cap))
    position_value = units * entry
    return {
        "capital": round(capital, 2),
        "risk_budget": round(risk_budget, 2),
        "risk_percent": round(risk_percent, 2),
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "risk_per_share": round(risk_per_share, 2),
        "units": round(units, 4),
        "position_value": round(position_value, 2),
        "position_percent": round(position_value / capital * 100.0, 2),
    }
