from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from tradingalgo.data.candles import Candle
from tradingalgo.intelligence.research_suite import (
    alert_signals,
    backtest_candles,
    portfolio_diagnostics,
    screen_analyses,
)


def _analysis(ticker: str, score: float, confidence: float, rsi: float = 55.0):
    return SimpleNamespace(
        ticker=ticker,
        score=score,
        confidence=confidence,
        action="BUY" if score >= 60 else "WATCH",
        technical_signals={
            "rsi14": rsi,
            "max_drawdown_pct": -10.0,
            "breakout_20d": "yes" if score >= 70 else "no",
            "macd_histogram": 0.25,
        },
    )


def test_screen_applies_multiple_filters():
    rows = [_analysis("AAA", 80, 0.8, 55), _analysis("BBB", 45, 0.9, 75)]
    result = screen_analyses(rows, min_score=60, max_rsi=70, breakout_only=True)
    assert [item.ticker for item in result] == ["AAA"]


def test_portfolio_diagnostics_reports_concentration():
    result = portfolio_diagnostics(
        {"AAA": 70, "BBB": 30},
        [_analysis("AAA", 80, 0.8), _analysis("BBB", 60, 0.7)],
    )
    assert result["largest_position_pct"] == 70.0
    assert "single-position concentration above 30%" in result["risk_flags"]
    assert result["weighted_score"] == 74.0


def test_alerts_are_deterministic():
    row = _analysis("AAA", 80, 0.8, 25)
    alerts = alert_signals(row)
    assert {item["type"] for item in alerts} >= {"oversold", "breakout", "macd"}


def test_backtest_rejects_short_history():
    candles = [Candle("AAA", date.today() - timedelta(days=i), 10, 11, 9, 10) for i in range(20)]
    with pytest.raises(ValueError, match="60 daily candles"):
        backtest_candles("AAA", sorted(candles, key=lambda x: x.session))


def test_backtest_produces_metrics():
    candles = []
    for i in range(120):
        price = 10.0 + i * 0.1
        session = date(2026, 1, 1) + timedelta(days=i)
        candles.append(Candle("AAA", session, price, price + 0.2, price - 0.1, price, 1000))
    result = backtest_candles("AAA", candles, "sma_cross")
    assert result.candles == 120
    assert result.buy_hold_return_pct > 0
    assert result.total_return_pct >= 0
