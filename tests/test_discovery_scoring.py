from tradingalgo.intelligence.discovery_scoring import DiscoveryPolicy, passes_filters, score_row


def test_short_and_long_models_weight_different_drivers():
    row = {
        "momentum": 90,
        "trend": 80,
        "relative_strength": 85,
        "liquidity": 70,
        "catalyst": 70,
        "fundamentals": 20,
        "market_regime": 70,
        "risk": 10,
    }
    short, _ = score_row(row, DiscoveryPolicy(horizon="short"))
    long, _ = score_row(row, DiscoveryPolicy(horizon="long"))
    assert short > long


def test_long_model_rewards_fundamentals_more_than_short_model():
    row = {
        "momentum": 30,
        "trend": 40,
        "relative_strength": 40,
        "liquidity": 60,
        "catalyst": 30,
        "fundamentals": 95,
        "market_regime": 60,
        "risk": 20,
    }
    short, _ = score_row(row, DiscoveryPolicy(horizon="short"))
    long, _ = score_row(row, DiscoveryPolicy(horizon="long"))
    assert long > short


def test_price_and_liquidity_filters_reject_low_quality_candidate():
    policy = DiscoveryPolicy(min_price=5, min_avg_volume=100_000, min_dollar_volume=2_000_000, min_evidence=3)
    accepted, reasons = passes_filters({
        "price": 2,
        "avg_volume": 50_000,
        "dollar_volume": 100_000,
        "evidence_count": 2,
    }, policy)
    assert not accepted
    assert "price filter" in reasons
    assert "liquidity filter" in reasons
    assert "dollar-volume filter" in reasons
    assert "minimum evidence filter" in reasons


def test_regime_and_sector_relative_strength_are_first_class_factors():
    score, factors = score_row({
        "momentum": 60,
        "trend": 60,
        "sector_relative_strength": 95,
        "liquidity": 60,
        "catalyst": 40,
        "fundamentals": 60,
        "market_regime": 90,
        "risk": 10,
    }, DiscoveryPolicy(horizon="short"))
    assert score > 60
    assert factors["relative_strength"] == 95
    assert factors["regime"] == 90
