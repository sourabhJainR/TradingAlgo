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


def _volumes(candles: Sequence[Any]) -> list[float]:
    return [float(item.volume or 0.0) for item in candles]


def _sma(values: Sequence[float], period: int) -> float | None:
    if not values:
        return None
    return mean(values[-period:])


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
    returns = [
        current / previous - 1.0
        for previous, current in zip(closes[:-1], closes[1:], strict=True)
        if previous
    ]
    return pstdev(returns) * sqrt(252.0) * 100.0 if len(returns) > 1 else None


def _pattern_signals(
    closes: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    volumes: Sequence[float],
) -> dict[str, float | str | None]:
    if len(closes) < 30:
        return {"trend_pattern": "insufficient_history"}
    sma20 = mean(closes[-20:])
    ema20 = _ema(closes, 20)
    price = closes[-1]
    recent = closes[-20:]
    recent_high = max(highs[-20:])
    recent_low = min(lows[-20:])
    prior_high = max(highs[-40:-20]) if len(highs) >= 40 else recent_high
    prior_low = min(lows[-40:-20]) if len(lows) >= 40 else recent_low
    avg_volume20 = mean(volumes[-20:]) if volumes else 0.0
    volume_ratio = volumes[-1] / avg_volume20 if avg_volume20 > 0 and volumes else None
    width = (max(recent) - min(recent)) / sma20 if sma20 else 0.0
    higher_highs = recent_high > prior_high * 1.005
    higher_lows = recent_low > prior_low * 1.005
    lower_highs = recent_high < prior_high * 0.995
    lower_lows = recent_low < prior_low * 0.995
    breakout = price >= recent_high * 0.995
    breakdown = price <= recent_low * 1.005
    double_top = abs(recent_high - prior_high) / max(recent_high, 1e-9) < 0.02 and price < sma20
    double_bottom = abs(recent_low - prior_low) / max(recent_low, 1e-9) < 0.02 and price > sma20
    if breakout and higher_lows:
        pattern = "bullish_breakout"
    elif breakdown and lower_highs:
        pattern = "bearish_breakdown"
    elif double_bottom:
        pattern = "double_bottom_candidate"
    elif double_top:
        pattern = "double_top_candidate"
    elif higher_highs and higher_lows:
        pattern = "higher_highs_higher_lows"
    elif lower_highs and lower_lows:
        pattern = "lower_highs_lower_lows"
    elif width < 0.08:
        pattern = "range_consolidation"
    else:
        pattern = "mixed_structure"
    return {
        "trend_pattern": pattern,
        "higher_highs": "yes" if higher_highs else "no",
        "higher_lows": "yes" if higher_lows else "no",
        "lower_highs": "yes" if lower_highs else "no",
        "lower_lows": "yes" if lower_lows else "no",
        "breakout_20d": "yes" if breakout else "no",
        "breakdown_20d": "yes" if breakdown else "no",
        "double_top_candidate": "yes" if double_top else "no",
        "double_bottom_candidate": "yes" if double_bottom else "no",
        "consolidation_width_pct": round(width * 100.0, 2),
        "volume_ratio_20d": round(volume_ratio, 2) if volume_ratio is not None else None,
        "ema20": round(ema20, 2) if ema20 is not None else None,
    }


def analyze(candles: Sequence[Any]) -> dict[str, float | str | None]:
    closes = _closes(candles)
    highs = _highs(candles)
    lows = _lows(candles)
    volumes = _volumes(candles)
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
    high52 = max(highs[-252:]) if highs else price
    low52 = min(closes[-252:]) if closes else price
    volatility = _annualized_volatility(closes)
    patterns = _pattern_signals(closes, highs, lows, volumes)
    sma50 = _sma(closes, 50)
    sma200 = _sma(closes, 200)
    return {
        "rsi14": round(rsi14, 2) if rsi14 is not None else None,
        "macd": round(macd, 4) if macd is not None else None,
        "macd_signal": round(macd_signal, 4) if macd_signal is not None else None,
        "macd_histogram": round(macd - macd_signal, 4) if macd is not None and macd_signal is not None else None,
        "bollinger_upper": round(upper, 2) if upper is not None else None,
        "bollinger_lower": round(lower, 2) if lower is not None else None,
        "atr14": round(atr14, 2) if atr14 is not None else None,
        "volatility_annualized_pct": round(volatility, 2) if volatility is not None else None,
        "max_drawdown_pct": round(_max_drawdown(closes), 2),
        "distance_from_52w_high_pct": round((price / high52 - 1.0) * 100.0, 2) if high52 else None,
        "distance_from_52w_low_pct": round((price / low52 - 1.0) * 100.0, 2) if low52 else None,
        "breakout_20d": patterns.get("breakout_20d", "no"),
        "oversold": "yes" if rsi14 is not None and rsi14 < 30 else "no",
        "overbought": "yes" if rsi14 is not None and rsi14 > 70 else "no",
        "sma20": round(sma20, 2) if sma20 is not None else None,
        "sma50": round(sma50, 2) if sma50 is not None else None,
        "sma200": round(sma200, 2) if sma200 is not None else None,
        "pattern": patterns.get("trend_pattern"),
        "higher_highs": patterns.get("higher_highs"),
        "higher_lows": patterns.get("higher_lows"),
        "lower_highs": patterns.get("lower_highs"),
        "lower_lows": patterns.get("lower_lows"),
        "breakdown_20d": patterns.get("breakdown_20d"),
        "double_top_candidate": patterns.get("double_top_candidate"),
        "double_bottom_candidate": patterns.get("double_bottom_candidate"),
        "consolidation_width_pct": patterns.get("consolidation_width_pct"),
        "volume_ratio_20d": patterns.get("volume_ratio_20d"),
        "ema20": patterns.get("ema20"),
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
