import pytest

from tradingalgo.web.market_recommendations import MarketRecommendations, asdict


def test_recommendation_limits_are_validated():
    from tradingalgo.web.market_recommendations import recommend_market

    with pytest.raises(ValueError):
        recommend_market("US", "short", limit=0)
    with pytest.raises(ValueError):
        recommend_market("US", "short", limit=2, recommendations=3)
    with pytest.raises(ValueError):
        recommend_market("Europe", "short")


def test_empty_result_serializes_as_advisory_only():
    result = MarketRecommendations(
        market="US",
        horizon="Short term",
        candidates_scanned=10,
        candidates_analyzed=0,
        recommendations=(),
        discovery_provider="twelve-data",
        warnings=("insufficient evidence",),
    )
    payload = asdict(result)
    assert payload["advisory_only"] is True
    assert payload["recommendations"] == []
    assert payload["candidates_scanned"] == 10
