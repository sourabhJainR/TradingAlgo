from tradingalgo.intelligence.macro import normalize_fred
from tradingalgo.intelligence.market_context import market_context, sector_signal


def test_fred_normalization_skips_invalid_values() -> None:
    rows = normalize_fred("CPI", {"observations": [{"date": "2026-01-01", "value": "3.1"}, {"value": "."}]})
    assert len(rows) == 1
    assert rows[0].value == 3.1


def test_market_context_and_sector_strength() -> None:
    context = market_context(110, 100, 70, 30, 0.5, 0.08, 0.03)
    assert context.index_vs_200dma_pct == 10.0
    assert context.breadth_pct == 70.0
    assert context.sector_relative_strength == 0.05
    assert sector_signal(context.sector_relative_strength) == 1.0
