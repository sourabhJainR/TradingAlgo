from datetime import date, timedelta

import pytest

from tradingalgo.data.candles import Candle
from tradingalgo.intelligence.technical_analytics import analyze, position_size


def _candles(count: int = 260) -> list[Candle]:
    rows = []
    for index in range(count):
        close = 100.0 + index * 0.5
        rows.append(Candle("TEST", date(2025, 1, 1) + timedelta(days=index), close - 0.5, close + 1.0, close - 1.0, close, 100000))
    return rows


def test_technical_analytics_returns_core_signals() -> None:
    result = analyze(_candles())
    assert result["rsi14"] is not None
    assert result["macd"] is not None
    assert result["macd_signal"] is not None
    assert result["atr14"] is not None
    assert result["volatility_annualized_pct"] is not None
    assert result["max_drawdown_pct"] == 0.0


def test_position_size_respects_risk_and_cap() -> None:
    result = position_size(100000, 1, 100, 95, 20)
    assert result["risk_budget"] == 1000
    assert result["units"] == 200
    assert result["position_value"] == 20000
    assert result["position_percent"] == 20


def test_position_size_rejects_invalid_long_stop() -> None:
    with pytest.raises(ValueError, match="stop must be below entry"):
        position_size(100000, 1, 100, 105)
