from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt
from statistics import mean, pstdev
from typing import Any, Iterable

from tradingalgo.data.candles import nse_historical, stooq_daily
from tradingalgo.data.sources import NsePublicSource, StooqSource


@dataclass(frozen=True)
class BacktestResult:
    ticker: str
    strategy: str
    candles: int
    trades: int
    total_return_pct: float
    cagr_pct: float
    sharpe: float
    max_drawdown_pct: float
    win_rate_pct: float
    profit_factor: float
    buy_hold_return_pct: float
    outperformed_buy_hold: bool


def _num(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def screen_analyses(
    analyses: Iterable[Any],
    *,
    min_score: float | None = None,
    min_confidence: float | None = None,
    action: str | None = None,
    min_rsi: float | None = None,
    max_rsi: float | None = None,
    max_drawdown: float | None = None,
    breakout_only: bool = False,
) -> list[Any]:
    wanted_action = action.strip().upper() if action else None
    selected: list[Any] = []
    for item in analyses:
        signals = getattr(item, "technical_signals", {}) or {}
        score = _num(getattr(item, "score", None))
        confidence = _num(getattr(item, "confidence", None))
        rsi = _num(signals.get("rsi14"))
        drawdown = _num(signals.get("max_drawdown_pct"))
        if min_score is not None and (score is None or score < min_score):
            continue
        if min_confidence is not None and (confidence is None or confidence < min_confidence):
            continue
        if wanted_action and str(getattr(item, "action", "")).upper() != wanted_action:
            continue
        if min_rsi is not None and (rsi is None or rsi < min_rsi):
            continue
        if max_rsi is not None and (rsi is None or rsi > max_rsi):
            continue
        if max_drawdown is not None and (drawdown is None or drawdown < max_drawdown):
            continue
        if breakout_only and signals.get("breakout_20d") != "yes":
            continue
        selected.append(item)
    return sorted(
        selected,
        key=lambda item: (
            _num(getattr(item, "score", None)) or -101.0,
            _num(getattr(item, "confidence", None)) or 0.0,
        ),
        reverse=True,
    )


def portfolio_diagnostics(positions: dict[str, float], analyses: Iterable[Any]) -> dict[str, Any]:
    clean = {str(ticker).upper(): max(0.0, float(weight)) for ticker, weight in positions.items()}
    total = sum(clean.values())
    if total <= 0:
        raise ValueError("portfolio weights must contain at least one positive value")
    weights = {ticker: weight / total for ticker, weight in clean.items()}
    by_ticker = {str(getattr(item, "ticker", "")).upper(): item for item in analyses}
    weighted_score = 0.0
    weighted_confidence = 0.0
    rows: list[dict[str, Any]] = []
    for ticker, weight in weights.items():
        item = by_ticker.get(ticker)
        score = _num(getattr(item, "score", None)) if item else None
        confidence = _num(getattr(item, "confidence", None)) if item else None
        if score is not None:
            weighted_score += score * weight
        if confidence is not None:
            weighted_confidence += confidence * weight
        rows.append({
            "ticker": ticker,
            "weight_pct": round(weight * 100.0, 2),
            "score": score,
            "confidence": confidence,
            "action": getattr(item, "action", "UNANALYZED") if item else "UNANALYZED",
        })
    hhi = sum(weight * weight for weight in weights.values())
    largest = max(weights.values())
    flags: list[str] = []
    if largest > 0.30:
        flags.append("single-position concentration above 30%")
    if hhi > 0.20:
        flags.append("portfolio concentration is high")
    if any(row["action"] == "AVOID" for row in rows if row["action"] != "UNANALYZED"):
        flags.append("one or more analyzed holdings are currently marked AVOID")
    return {
        "positions": rows,
        "weighted_score": round(weighted_score, 2),
        "weighted_confidence": round(weighted_confidence, 4),
        "concentration_hhi": round(hhi, 4),
        "largest_position_pct": round(largest * 100.0, 2),
        "risk_flags": flags,
        "advisory_only": True,
    }


def alert_signals(analysis: Any) -> list[dict[str, str]]:
    signals = getattr(analysis, "technical_signals", {}) or {}
    alerts: list[dict[str, str]] = []
    rsi = _num(signals.get("rsi14"))
    if rsi is not None and rsi < 30:
        alerts.append({"type": "oversold", "severity": "watch", "message": f"RSI(14) is {rsi:.1f}, below 30."})
    if rsi is not None and rsi > 70:
        alerts.append({"type": "overbought", "severity": "watch", "message": f"RSI(14) is {rsi:.1f}, above 70."})
    histogram = _num(signals.get("macd_histogram"))
    if histogram is not None:
        alerts.append({"type": "macd", "severity": "positive" if histogram > 0 else "negative", "message": f"MACD histogram is {histogram:.4f}."})
    if signals.get("breakout_20d") == "yes":
        alerts.append({"type": "breakout", "severity": "positive", "message": "Price is within 0.5% of the 20-day high breakout level."})
    drawdown = _num(signals.get("max_drawdown_pct"))
    if drawdown is not None and drawdown <= -25:
        alerts.append({"type": "drawdown", "severity": "warning", "message": f"Maximum observed drawdown is {drawdown:.1f}%."})
    return alerts


def _sma(values: list[float], period: int) -> float:
    return mean(values[-period:])


def _signal(closes: list[float], index: int, strategy: str) -> bool:
    if strategy == "sma_cross":
        if index < 50:
            return False
        return _sma(closes[: index + 1], 20) > _sma(closes[: index + 1], 50)
    if strategy == "breakout":
        if index < 20:
            return False
        return closes[index] >= max(closes[index - 20 : index])
    if strategy == "mean_reversion":
        if index < 20:
            return False
        return closes[index] < _sma(closes[: index + 1], 20) * 0.97
    raise ValueError("strategy must be sma_cross, breakout or mean_reversion")


def _metrics(daily_returns: list[float], equity: list[float], years: float) -> tuple[float, float, float, float]:
    total = equity[-1] - 1.0
    cagr = (equity[-1] ** (1.0 / years) - 1.0) if years > 0 and equity[-1] > 0 else -1.0
    volatility = pstdev(daily_returns) * sqrt(252.0) if len(daily_returns) > 1 else 0.0
    sharpe = (mean(daily_returns) * 252.0 / volatility) if volatility > 0 else 0.0
    peak = 1.0
    drawdown = 0.0
    for value in equity:
        peak = max(peak, value)
        drawdown = min(drawdown, value / peak - 1.0)
    return total * 100.0, cagr * 100.0, sharpe, drawdown * 100.0


def backtest_candles(ticker: str, candles: list[Any], strategy: str = "sma_cross") -> BacktestResult:
    if len(candles) < 60:
        raise ValueError("at least 60 daily candles are required for backtesting")
    closes = [float(item.close) for item in candles]
    equity = [1.0]
    daily_returns: list[float] = []
    trade_returns: list[float] = []
    position = False
    entry = 0.0
    for index in range(1, len(closes)):
        signal = _signal(closes, index - 1, strategy)
        if signal and not position:
            position = True
            entry = closes[index]
        if not signal and position:
            trade_returns.append(closes[index] / entry - 1.0)
            position = False
        daily = closes[index] / closes[index - 1] - 1.0 if position else 0.0
        daily_returns.append(daily)
        equity.append(equity[-1] * (1.0 + daily))
    if position:
        trade_returns.append(closes[-1] / entry - 1.0)
    years = max((candles[-1].session - candles[0].session).days / 365.25, 1.0 / 365.25)
    total, cagr, sharpe, drawdown = _metrics(daily_returns, equity, years)
    wins = [value for value in trade_returns if value > 0]
    losses = [value for value in trade_returns if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss else float("inf") if wins else 0.0
    buy_hold = closes[-1] / closes[0] - 1.0
    return BacktestResult(
        ticker=ticker.upper(),
        strategy=strategy,
        candles=len(candles),
        trades=len(trade_returns),
        total_return_pct=round(total, 2),
        cagr_pct=round(cagr * 1.0, 2),
        sharpe=round(sharpe, 3),
        max_drawdown_pct=round(drawdown, 2),
        win_rate_pct=round(len(wins) / len(trade_returns) * 100.0, 2) if trade_returns else 0.0,
        profit_factor=round(profit_factor, 3) if profit_factor != float("inf") else 999.0,
        buy_hold_return_pct=round(buy_hold * 100.0, 2),
        outperformed_buy_hold=total > buy_hold * 100.0,
    )


def backtest_symbol(ticker: str, market: str, strategy: str = "sma_cross", days: int = 750) -> BacktestResult:
    symbol = ticker.strip().upper()
    if not symbol:
        raise ValueError("ticker is required")
    market_key = market.strip().lower()
    if market_key == "us":
        payload = StooqSource().daily(symbol, days=days).payload
        candles = stooq_daily(symbol, payload)
    elif market_key == "india":
        payload = NsePublicSource().historical(symbol, days=days).payload
        candles = nse_historical(symbol, payload)
    else:
        raise ValueError("market must be US or India")
    return backtest_candles(symbol, candles, strategy)


def backtest_dict(result: BacktestResult) -> dict[str, Any]:
    return {**asdict(result), "advisory_only": True, "note": "Historical simulation is not a forecast and excludes brokerage/taxes unless explicitly modeled."}
