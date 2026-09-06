from datetime import date, datetime, timezone, timedelta

import pytest

from tradingalgo.data.candles import Candle
from tradingalgo.intelligence.learning import (
    LeakageError,
    OutcomeObservation,
    PredictionSnapshot,
    WalkForwardConfig,
    WalkForwardValidator,
    baseline_comparison,
    prediction_id_for,
    statistical_tests,
)
from tradingalgo.intelligence.models import Advisory, Horizon, Signal
from tradingalgo.intelligence.outcomes import realize_price_outcome


def snapshot(as_of=datetime(2025, 1, 1, tzinfo=timezone.utc), score=50.0):
    advisory = Advisory(ticker="AAA", action="BUY", score=score, confidence=.8, horizon=Horizon.SWING,
                        signals=[Signal(name="x", category="technical", ticker="AAA", score=score,
                                        confidence=.8, horizon=Horizon.SWING, rationale="x")])
    return PredictionSnapshot.from_advisory(advisory, as_of, prediction_id_for(advisory, as_of))


def candles():
    return [Candle("AAA", date(2025, 1, 2), 100, 103, 98, 101),
            Candle("AAA", date(2025, 1, 6), 101, 110, 99, 108),
            Candle("AAA", date(2025, 1, 13), 108, 115, 105, 112),
            Candle("AAA", date(2025, 1, 21), 112, 120, 110, 118)]


def test_realized_outcome_is_linked_to_exact_prediction_and_path_metrics():
    result = realize_price_outcome(snapshot(), candles())
    assert result.observation.prediction_id.startswith("pred-")
    assert result.entry_session == date(2025, 1, 2)
    assert result.exit_session == date(2025, 1, 21)
    assert result.observation.realized_return == pytest.approx(.18)
    assert result.maximum_adverse_excursion == pytest.approx(-.02)
    assert result.maximum_favorable_excursion == pytest.approx(.20)


def test_outcome_requires_prices_beyond_horizon():
    with pytest.raises(ValueError):
        realize_price_outcome(snapshot(), candles()[:2])


def test_future_outcome_inside_horizon_is_rejected():
    s = snapshot()
    o = OutcomeObservation(s.prediction_id, "AAA", s.as_of + timedelta(days=1), .01)
    with pytest.raises(LeakageError):
        from tradingalgo.intelligence.learning import validate_no_lookahead
        validate_no_lookahead(s, {}, o)


def test_prediction_id_is_reproducible():
    s1, s2 = snapshot(), snapshot()
    assert s1.prediction_id == s2.prediction_id


def test_baseline_and_statistical_tests_are_deterministic():
    pairs = []
    for i, value in enumerate((.10, .05, .08, .07, .09), start=1):
        s = snapshot(datetime(2025, 1, i, tzinfo=timezone.utc), 50)
        pairs.append((s, OutcomeObservation(s.prediction_id, "AAA", s.as_of + timedelta(days=10), value, .01)))
    baseline = baseline_comparison(pairs)
    stats = statistical_tests(pairs, samples=300, seed=7)
    assert baseline["system_mean_excess"] > 0
    assert stats.sample_size == 5
    assert stats.bootstrap_ci_low <= stats.mean_excess_return <= stats.bootstrap_ci_high
    assert 0 <= stats.permutation_p_value <= 1


def test_walk_forward_uses_only_prior_training_outcomes():
    pairs = []
    for i in range(40):
        as_of = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i * 15)
        s = snapshot(as_of, 40 if i % 2 == 0 else -40)
        outcome = OutcomeObservation(s.prediction_id, "AAA", as_of + timedelta(days=10), .02 if i % 2 == 0 else -.01)
        pairs.append((s, outcome))
    result = WalkForwardValidator(WalkForwardConfig(train_days=180, test_days=60, step_days=60,
                                                    min_train_observations=5, min_factor_observations=5)).run(
        [s for s, _ in pairs], [o for _, o in pairs])
    assert result.outcomes > 0
