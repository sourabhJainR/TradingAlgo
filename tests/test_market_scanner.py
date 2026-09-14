from datetime import datetime, timezone

import pytest

from tradingalgo.data.health import ProviderHealthRegistry
from tradingalgo.data.providers import ProviderResponse
from tradingalgo.intelligence.market_scanner import MarketDiscovery


def response(payload):
    return ProviderResponse(
        provider="screen",
        endpoint="test://screen",
        fetched_at=datetime.now(timezone.utc),
        payload=payload,
    )


def test_discovery_ranks_candidates_and_respects_limit():
    scanner = MarketDiscovery(ProviderHealthRegistry())
    result = scanner.discover(
        lambda: response([
            {"symbol": "AAA", "score": 20},
            {"symbol": "BBB", "score": 80},
            {"symbol": "CCC", "score": 60},
        ]),
        provider="screen",
        limit=2,
    )

    assert [item.ticker for item in result.candidates] == ["BBB", "CCC"]
    assert result.provider == "screen"
    assert not result.errors


def test_discovery_computes_transparent_score_when_provider_does_not_supply_one():
    scanner = MarketDiscovery(ProviderHealthRegistry())
    result = scanner.discover(
        lambda: response([
            {"symbol": "AAA", "momentum": 90, "trend": 80, "fundamentals": 70, "catalyst": 60, "liquidity": 50, "risk": 10},
            {"symbol": "BBB", "momentum": 50, "trend": 50, "fundamentals": 50, "catalyst": 50, "liquidity": 50, "risk": 10},
        ]),
        provider="screen",
    )

    assert result.candidates[0].ticker == "AAA"
    assert result.candidates[0].score > result.candidates[1].score


def test_discovery_rejects_invalid_limit():
    scanner = MarketDiscovery(ProviderHealthRegistry())
    with pytest.raises(ValueError):
        scanner.discover(lambda: response([]), limit=0)


def test_discovery_does_not_invent_symbols_on_provider_failure():
    scanner = MarketDiscovery(ProviderHealthRegistry())
    result = scanner.discover(lambda: (_ for _ in ()).throw(RuntimeError("down")), provider="screen")

    assert result.candidates == ()
    assert "screen" in result.errors
