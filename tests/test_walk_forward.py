from datetime import datetime, timedelta, timezone

import pytest

from tradingalgo.intelligence.learning import LeakageError, OutcomeObservation, PredictionSnapshot
from tradingalgo.intelligence.models import Horizon
from tradingalgo.intelligence.validation import ValidationConfig, walk_forward

BASE = datetime(2024, 1, 1, tzinfo=timezone.utc)


def make_snapshot(day: int, score: float = 50.0) -> PredictionSnapshot:
    return PredictionSnapshot(f"p{day}", "AAA", BASE + timedelta(days=day), "BUY" if score > 0 else "AVOID",
                              score, .8, Horizon.SWING, (f"e{day}",), {"technical": score, "fundamental": score / 2})


def make_outcome(snapshot: PredictionSnapshot, ret: float) -> OutcomeObservation:
    return OutcomeObservation(snapshot.prediction_id, "AAA", snapshot.as_of + timedelta(days=10), ret)


def test_walk_forward_only_calibrates_from_outcomes_realized_before_fold():
    snapshots = [make_snapshot(i, 50 if i % 2 else -50) for i in range(1, 121)]
    outcomes = [make_outcome(s, .02 if s.score > 0 else -.02) for s in snapshots]
    result = walk_forward(snapshots, outcomes,
                          ValidationConfig(train_days=30, test_days=15, step_days=15,
                                           min_train_observations=5, min_factor_observations=5))
    assert result.predictions > 0
    assert result.directional_accuracy >= .5
    assert result.mean_excess_return > 0


def test_future_evidence_is_rejected_before_validation():
    s = make_snapshot(1)
    o = make_outcome(s, .02)
    with pytest.raises(LeakageError):
        walk_forward([s], [o], ValidationConfig(train_days=1, min_train_observations=1),
                     {"e1": s.as_of + timedelta(minutes=1)})
