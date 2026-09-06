from tradingalgo.intelligence.technical import snapshot
from tradingalgo.intelligence.technical_signals import build_technical_signal


def test_technical_signal_is_bullish_for_rising_series():
    technical = snapshot([float(i) for i in range(1, 221)])
    signal = build_technical_signal("NVDA", technical)
    assert signal.ticker == "NVDA"
    assert signal.category == "technical"
    assert signal.score > 0
    assert signal.confidence > 0
    assert signal.evidence_ids == []


def test_technical_signal_handles_short_series():
    signal = build_technical_signal("MU", snapshot([100.0, 99.0, 98.0]))
    assert signal.ticker == "MU"
    assert -100 <= signal.score <= 100
