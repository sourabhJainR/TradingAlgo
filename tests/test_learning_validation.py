from datetime import datetime, timedelta, timezone

import pytest

from tradingalgo.intelligence.learning import (
    FactorCalibrator,
    LeakageError,
    OutcomeObservation,
    PredictionSnapshot,
    WalkForwardConfig,
    WalkForwardValidator,
    apply_factor_weights,
    validate_no_lookahead,
)
from tradingalgo.intelligence.models import Advisory, Horizon, Signal


NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)


def snapshot(day: int, score: float = 40.0, action: str = "BUY") -> PredictionSnapshot:
    return PredictionSnapshot(
        prediction_id=f"p{day}", ticker="AAA", as_of=NOW + timedelta(days=day),
        action=action, score=score, confidence=.8, horizon=Horizon.SWING,
        evidence_ids=(f"e{day}",), factor_scores={"technical": score, "fundamental": score / 2},
    )


def outcome(s: PredictionSnapshot, ret: float) -> OutcomeObservation:
    return OutcomeObservation(s.prediction_id, s.ticker, s.as_of + timedelta(days=10), ret, 0.0, -0.05)


def test_snapshot_captures_advisory_provenance():
    advisory = Advisory(
        ticker="aaa", action="BUY", score=42, confidence=.8, horizon=Horizon.SWING,
        signals=[Signal(name="technical", category="technical", ticker="AAA", score=42,
                        confidence=.8, horizon=Horizon.SWING, rationale="trend", evidence_ids=["e1"])]
    )
    result = PredictionSnapshot.from_advisory(advisory, NOW, "p1")
    assert result.ticker == "AAA"
    assert result.evidence_ids == ("e1",)
    assert result.factor_scores["technical"] == 42


def test_future_evidence_is_rejected():
    s = snapshot(0)
    o = outcome(s, .1)
    with pytest.raises(LeakageError):
        validate_no_lookahead(s, {"e0": NOW + timedelta(minutes=1)}, o)


def test_outcome_before_horizon_is_rejected():
    s = snapshot(0)
    o = OutcomeObservation(s.prediction_id, "AAA", NOW + timedelta(days=9), .1)
    with pytest.raises(LeakageError):
        validate_no_lookahead(s, {}, o)


def test_factor_calibration_uses_return_correlation_and_stays_bounded():
    snapshots = [snapshot(i, 20 + i) for i in range(1, 8)]
    outcomes = [outcome(s, .01 * i) for i, s in enumerate(snapshots, 1)]
    weights = FactorCalibrator(strength=1.0).fit(snapshots, outcomes)
    assert weights
    assert all(.5 <= value <= 1.5 for value in weights.values())
    adjusted = apply_factor_weights(snapshots[0], weights)
    assert -100 <= adjusted.score <= 100


def test_walk_forward_is_strictly_out_of_sample():
    snapshots = [snapshot(i, 50 if i % 2 else -50, "BUY" if i % 2 else "AVOID") for i in range(1, 121)]
    outcomes = [outcome(s, .02 if s.score > 0 else -.02) for s in snapshots]
    result = WalkForwardValidator(WalkForwardConfig(train_days=30, test_days=15, step_days=15,
                                                     min_train_observations=5)).run(snapshots, outcomes)
    assert result.predictions > 0
    assert result.outcomes == result.predictions
    assert result.directional_accuracy >= .5
    assert result.mean_excess_return > 0
