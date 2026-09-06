from datetime import date

from tradingalgo.data.candles import alpha_vantage_daily, finnhub_candles
from tradingalgo.data.health import ProviderHealthRegistry


def test_alpha_vantage_candles_are_sorted() -> None:
    payload = {"Time Series (Daily)": {"2026-01-02": {"1. open": "10", "2. high": "12", "3. low": "9", "4. close": "11", "5. volume": "100"}, "2026-01-01": {"1. open": "9", "2. high": "10", "3. low": "8", "4. close": "9.5", "5. volume": "90"}}}
    candles = alpha_vantage_daily("ABC", payload)
    assert [c.session for c in candles] == [date(2026, 1, 1), date(2026, 1, 2)]
    assert candles[-1].close == 11


def test_finnhub_candles() -> None:
    candles = finnhub_candles("ABC", {"s": "ok", "t": [1767225600], "o": [10], "h": [12], "l": [9], "c": [11], "v": [100]})
    assert len(candles) == 1
    assert candles[0].close == 11


def test_health_registry_recovers_after_success() -> None:
    registry = ProviderHealthRegistry()
    for _ in range(3):
        registry.record_failure("demo")
    assert not registry.get("demo").available
    registry.record_success("demo")
    assert registry.get("demo").available
    assert registry.get("demo").success_rate == 0.25
