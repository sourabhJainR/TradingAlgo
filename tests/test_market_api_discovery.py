from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tradingalgo.data.market_apis import AlphaVantageProvider
from tradingalgo.data.providers import ProviderResponse
from tradingalgo.intelligence.market_api_discovery import alpha_vantage_universe


def test_alpha_vantage_us_movers_are_normalized() -> None:
    class FakeProvider:
        def top_gainers_losers(self) -> ProviderResponse:
            return ProviderResponse(
                "alpha-vantage",
                "https://example/query",
                datetime.now(timezone.utc),
                {
                    "top_gainers": [{"ticker": "ABC", "change_percentage": "12.5%", "volume": "2000000"}],
                    "most_actively_traded": [{"ticker": "XYZ", "change_percentage": "1.0%", "volume": "60000000"}],
                },
            )

    rows = alpha_vantage_universe(FakeProvider(), market="us")().payload
    assert rows[0]["ticker"] == "ABC"
    assert rows[0]["momentum"] == 12.5
    assert rows[1]["liquidity"] == 100.0


def test_alpha_vantage_rejects_india_discovery() -> None:
    provider = object.__new__(AlphaVantageProvider)
    with pytest.raises(ValueError, match="US equities"):
        alpha_vantage_universe(provider, market="india")
