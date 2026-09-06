"""Leakage-safe walk-forward validation and factor calibration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Mapping, Sequence

from .learning import HORIZON_DAYS, LeakageError, OutcomeObservation, PredictionSnapshot


@dataclass(frozen=True)
class ValidationConfig:
    train_days: int = 365
    test_days: int = 90
    step_days: int = 30
    embargo_days: int = 0
    min_train_observations: int = 20
    min_factor_observations: int = 20
    min_weight: float = 0.5
    max_weight: float = 1.5
    calibration_strength: float = 0.5


@dataclass(frozen=True)
class ValidationResult:
    predictions: int
    outcomes: int
    directional_accuracy: float
    mean_excess_return: float
    mean_return: float
    mean_max_drawdown: float
    brier_score: float
    calibration_error: float
    by_action: Mapping[str, Mapping[str, float]]
    factor_weights: Mapping[str, float]


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def assert_prediction_safe(snapshot: PredictionSnapshot, evidence_observed_at: Mapping[str, datetime]) -> None:
    for evidence_id in snapshot.evidence_ids:
        observed = evidence_observed_at.get(evidence_id)
        if observed is not None and _utc(observed) > _utc(snapshot.as_of):
            raise LeakageError(f"evidence {evidence_id} observed after prediction as_of")


def assert_outcome_safe(snapshot: PredictionSnapshot, outcome: OutcomeObservation) -> None:
    if outcome.ticker.upper() != snapshot.ticker.upper():
        raise LeakageError("prediction/outcome ticker mismatch")
    minimum = _utc(snapshot.as_of) + timedelta(days=HORIZON_DAYS[snapshot.horizon])
    if _utc(outcome.observed_at) < minimum:
        raise LeakageError("outcome is inside the prediction horizon")


def calibrate_factors(snapshots: Sequence[PredictionSnapshot], outcomes: Sequence[OutcomeObservation],
                     config: ValidationConfig) -> dict[str, float]:
    outcome_by_id = {o.prediction_id: o for o in outcomes}
    pairs: dict[str, list[tuple[float, float]]] = {}
    for snapshot in snapshots:
        outcome = outcome_by_id.get(snapshot.prediction_id)
        if outcome is None or _utc(outcome.observed_at) > max(_utc(o.observed_at) for o in outcomes if o.prediction_id == snapshot.prediction_id):
            continue
        for factor, score in snapshot.factor_scores.items():
            pairs.setdefault(factor, []).append((float(score), outcome.excess_return))
    raw = {factor: _bounded_correlation_weight(values, config)
           for factor, values in pairs.items() if len(values) >= config.min_factor_observations}
    if not raw:
        return {}
    center = mean(raw.values())
    return {factor: max(config.min_weight, min(config.max_weight, weight / center)) for factor, weight in raw.items()}


def _bounded_correlation_weight(pairs: Sequence[tuple[float, float]], config: ValidationConfig) -> float:
    xs, ys = [x for x, _ in pairs], [y for _, y in pairs]
    mx, my = mean(xs), mean(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return 1.0
    corr = sum((x - mx) * (y - my) for x, y in pairs) / (vx * vy) ** 0.5
    return max(config.min_weight, min(config.max_weight, 1.0 + config.calibration_strength * corr))


def _weighted_score(snapshot: PredictionSnapshot, weights: Mapping[str, float]) -> float:
    if not weights:
        return snapshot.score
    denominator = sum(abs(weights.get(factor, 1.0)) for factor in snapshot.factor_scores) or 1.0
    return max(-100.0, min(100.0, sum(score * weights.get(factor, 1.0)
                                             for factor, score in snapshot.factor_scores.items()) / denominator))


def walk_forward(snapshots: Sequence[PredictionSnapshot], outcomes: Sequence[OutcomeObservation],
                 config: ValidationConfig | None = None,
                 evidence_observed_at: Mapping[str, datetime] | None = None) -> ValidationResult:
    """Run strictly out-of-sample folds; each fold calibrates only from already-realized outcomes."""
    cfg = config or ValidationConfig()
    ordered = sorted(snapshots, key=lambda s: _utc(s.as_of))
    outcome_by_id = {o.prediction_id: o for o in outcomes}
    evidence = evidence_observed_at or {}
    for snapshot in ordered:
        assert_prediction_safe(snapshot, evidence)
        outcome = outcome_by_id.get(snapshot.prediction_id)
        if outcome is not None:
            assert_outcome_safe(snapshot, outcome)
    if not ordered:
        return ValidationResult(0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, {}, {})

    cursor = _utc(ordered[0].as_of) + timedelta(days=cfg.train_days)
    last = _utc(ordered[-1].as_of)
    evaluated: list[tuple[PredictionSnapshot, OutcomeObservation]] = []
    fold_weights: list[Mapping[str, float]] = []
    while cursor <= last:
        train_start = cursor - timedelta(days=cfg.train_days)
        test_start = cursor + timedelta(days=cfg.embargo_days)
        test_end = test_start + timedelta(days=cfg.test_days)
        train = [s for s in ordered if train_start <= _utc(s.as_of) < cursor]
        train_outcomes = [outcome_by_id[s.prediction_id] for s in train
                          if s.prediction_id in outcome_by_id and _utc(outcome_by_id[s.prediction_id].observed_at) < cursor]
        test = [s for s in ordered if test_start <= _utc(s.as_of) < test_end]
        if len(train_outcomes) >= cfg.min_train_observations:
            weights = calibrate_factors(train, train_outcomes, cfg)
            fold_weights.append(weights)
            for snapshot in test:
                outcome = outcome_by_id.get(snapshot.prediction_id)
                if outcome is not None:
                    evaluated.append((snapshot, outcome))
        cursor += timedelta(days=cfg.step_days)

    weights = _average_weights(fold_weights)
    return _metrics([(s, o, _weighted_score(s, weights)) for s, o in evaluated], weights)


def _metrics(pairs: Sequence[tuple[PredictionSnapshot, OutcomeObservation, float]], weights: Mapping[str, float]) -> ValidationResult:
    if not pairs:
        return ValidationResult(0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, {}, dict(weights))
    correct = 0
    brier: list[float] = []
    action_returns: dict[str, list[float]] = {}
    for snapshot, outcome, score in pairs:
        direction = 1 if score > 0 else -1 if score < 0 else 0
        actual = 1 if outcome.excess_return > 0 else -1 if outcome.excess_return < 0 else 0
        correct += direction == actual
        probability = 0.5 + 0.5 * max(-1.0, min(1.0, score / 100.0))
        brier.append((probability - float(actual > 0)) ** 2)
        action_returns.setdefault(snapshot.action, []).append(outcome.excess_return)
    action_metrics = {a: {"count": float(len(v)), "mean_excess_return": mean(v)} for a, v in action_returns.items()}
    return ValidationResult(len(pairs), len(pairs), correct / len(pairs),
                            mean(o.excess_return for _, o, _ in pairs), mean(o.realized_return for _, o, _ in pairs),
                            mean(o.max_drawdown for _, o, _ in pairs), mean(brier),
                            abs(mean(s.confidence for s, _, _ in pairs) - correct / len(pairs)), action_metrics, dict(weights))


def _average_weights(rows: Sequence[Mapping[str, float]]) -> dict[str, float]:
    factors = {factor for row in rows for factor in row}
    return {factor: mean(row[factor] for row in rows if factor in row) for factor in factors}
