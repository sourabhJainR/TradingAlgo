from datetime import date, datetime, timezone

from tradingalgo.data.candles import Candle
from tradingalgo.intelligence.backtesting import BacktestConfig, run_backtest
from tradingalgo.intelligence.ipo_analysis import analyze_ipo, build_ipo_profile
from tradingalgo.intelligence.learning import PredictionSnapshot
from tradingalgo.intelligence.models import Horizon


def candles(n=230):
    return [Candle("TEST", date(2025, 1, 1).fromordinal(date(2025, 1, 1).toordinal() + i), 100 + i, 101 + i, 99 + i, 100 + i, 1000) for i in range(n)]


def predictor(as_of, history):
    return PredictionSnapshot("p-" + as_of.isoformat(), "TEST", datetime.combine(as_of, datetime.min.time(), timezone.utc), "BUY", 50, .8, Horizon.SWING, (), {"technical": 50.0})


def test_backtest_is_chronological_and_produces_trades():
    report = run_backtest("TEST", candles(), predictor, config=BacktestConfig(warmup_sessions=200, rebalance_every_sessions=5))
    assert report.trades > 0
    assert report.cumulative_return > 0
    assert 0 <= report.hit_rate <= 1


def test_ipo_missing_data_reduces_confidence():
    profile = build_ipo_profile("NEW", "NewCo", {"revenue_growth": .60, "cash": 100, "debt": 20})
    result = analyze_ipo(profile)
    assert result.score > 50
    assert result.confidence < 1
    assert "operating_margin" in result.missing_data


def test_ipo_public_record_risk_is_bearish():
    profile = build_ipo_profile("RISK", "RiskCo", {
        "revenue_growth": .10, "operating_margin": -.10, "free_cash_flow_margin": -.20,
        "cash": 10, "debt": 100, "dilution_pct": 40, "customer_concentration_pct": 80,
        "litigation_risk": 1, "regulatory_risk": 1, "governance_risk": 1, "related_party_risk": 1,
    })
    result = analyze_ipo(profile)
    assert result.verdict == "AVOID"
    assert result.risks
