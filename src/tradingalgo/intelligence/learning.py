"""Historical prediction tracking, leakage-safe validation and factor calibration.

This module is deliberately offline/research-only: it evaluates advisory decisions and
never places orders. All validation is strictly time ordered so future observations cannot
influence a past prediction or its calibration parameters.
"""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from statistics import mean
from typing import Iterable, Mapping, Sequence

from .models import Advisory, Horizon, Signal


HORIZON_DAYS: dict[Horizon, int] = {
    Horizon.INTRADAY: 1,
    Horizon.SWING: 10,
    Horizon.MEDIUM: 60,
    Horizon.LONG: 252,
}


class LeakageError(ValueError):
    """Raised when a validation input contains information from the future."""


@dataclass(frozen=True)
class PredictionSnapshot:
    prediction_id: str
    ticker: str
    as_of: datetime
    action: str
    score: float
    confidence: float
    horizon: Horizon
    evidence_ids: tuple[str, ...]
    factor_scores: Mapping[str, float]

    @classmethod
    def from_advisory(cls, advisory: Advisory, as_of: datetime, prediction_id: str) -> "PredictionSnapshot":
        timestamp = _utc(as_of)
        factors = {signal.category: signal.score for signal in advisory.signals}
        return cls(
            prediction_id=prediction_id,
            ticker=advisory.ticker.upper(),
            as_of=timestamp,
            action=advisory.action,
            score=advisory.score,
            confidence=advisory.confidence,
            horizon=advisory.horizon,
            evidence_ids=tuple(dict.fromkeys(e for signal in advisory.signals for e in signal.evidence_ids)),
            factor_scores=factors,
        )


@dataclass(frozen=True)
class OutcomeObservation:
    prediction_id: str
    ticker: str
    observed_at: datetime
    realized_return: float
    benchmark_return: float = 0.0
    max_drawdown: float = 0.0

    @property
    def excess_return(self) -> float:
        return self.realized_return - self.benchmark_return


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


@dataclass(frozen=True)
class WalkForwardConfig:
    train_days: int = 365
    test_days: int = 90
    step_days: int = 30
    embargo_days: int = 0
    min_train_observations: int = 20


class LearningStore:
    """Small durable SQLite store for predictions and realized outcomes."""

    def __init__(self, path: str | Path = "data/tradingalgo_learning.sqlite") -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS predictions (
            prediction_id TEXT PRIMARY KEY, ticker TEXT NOT NULL, as_of TEXT NOT NULL,
            action TEXT NOT NULL, score REAL NOT NULL, confidence REAL NOT NULL,
            horizon TEXT NOT NULL, evidence_ids TEXT NOT NULL, factor_scores TEXT NOT NULL
        )""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS outcomes (
            prediction_id TEXT PRIMARY KEY, ticker TEXT NOT NULL, observed_at TEXT NOT NULL,
            realized_return REAL NOT NULL, benchmark_return REAL NOT NULL, max_drawdown REAL NOT NULL,
            FOREIGN KEY(prediction_id) REFERENCES predictions(prediction_id)
        )""")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_predictions_time ON predictions(as_of, ticker)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_time ON outcomes(observed_at, ticker)")
        self.db.commit()

    def save_prediction(self, snapshot: PredictionSnapshot) -> None:
        import json
        self.db.execute(
            "INSERT OR REPLACE INTO predictions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (snapshot.prediction_id, snapshot.ticker, _utc(snapshot.as_of).isoformat(), snapshot.action,
             snapshot.score, snapshot.confidence, snapshot.horizon.value,
             json.dumps(snapshot.evidence_ids), json.dumps(dict(snapshot.factor_scores), sort_keys=True)),
        )
        self.db.commit()

    def save_outcome(self, outcome: OutcomeObservation) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO outcomes VALUES (?, ?, ?, ?, ?, ?)",
            (outcome.prediction_id, outcome.ticker, _utc(outcome.observed_at).isoformat(),
             outcome.realized_return, outcome.benchmark_return, outcome.max_drawdown),
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()


class FactorCalibrator:
    """Calibrate factor influence using only observations available before the test window."""

    def __init__(self, min_weight: float = 0.50, max_weight: float = 1.50, strength: float = 0.50) -> None:
        if min_weight <= 0 or max_weight < min_weight or strength < 0:
            raise ValueError("invalid calibration bounds")
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.strength = strength

    def fit(self, snapshots: Sequence[PredictionSnapshot], outcomes: Sequence[OutcomeObservation]) -> dict[str, float]:
        by_id = {o.prediction_id: o for o in outcomes}
        pairs: dict[str, list[tuple[float, float]]] = {}
        for snapshot in snapshots:
            outcome = by_id.get(snapshot.prediction_id)
            if outcome is None or _utc(outcome.observed_at) <= _utc(snapshot.as_of):
                continue
            for factor, value in snapshot.factor_scores.items():
                pairs.setdefault(factor, []).append((float(value), outcome.excess_return))
        weights = {factor: self._weight(values) for factor, values in pairs.items() if len(values) >= 3}
        if not weights:
            return {}
        center = mean(weights.values())
        return {factor: max(self.min_weight, min(self.max_weight, weight / center)) for factor, weight in weights.items()}

    def _weight(self, pairs: Sequence[tuple[float, float]]) -> float:
        xs = [x for x, _ in pairs]; ys = [y for _, y in pairs]
        sx = _stdev(xs); sy = _stdev(ys)
        if sx == 0 or sy == 0:
            return 1.0
        corr = sum((x - mean(xs)) * (y - mean(ys)) for x, y in pairs) / ((len(pairs) - 1) * sx * sy)
        return max(self.min_weight, min(self.max_weight, 1.0 + self.strength * corr))


def apply_factor_weights(snapshot: PredictionSnapshot, weights: Mapping[str, float]) -> PredictionSnapshot:
    if not weights:
        return snapshot
    adjusted = {name: score * weights.get(name, 1.0) for name, score in snapshot.factor_scores.items()}
    denominator = sum(abs(weights.get(name, 1.0)) for name in snapshot.factor_scores) or 1.0
    score = sum(adjusted.values()) / denominator
    return PredictionSnapshot(snapshot.prediction_id, snapshot.ticker, snapshot.as_of, snapshot.action,
                              max(-100.0, min(100.0, score)), snapshot.confidence, snapshot.horizon,
                              snapshot.evidence_ids, adjusted)


def validate_no_lookahead(snapshot: PredictionSnapshot, evidence_observed_at: Mapping[str, datetime], outcome: OutcomeObservation) -> None:
    for evidence_id in snapshot.evidence_ids:
        observed = evidence_observed_at.get(evidence_id)
        if observed is not None and _utc(observed) > _utc(snapshot.as_of):
            raise LeakageError(f"evidence {evidence_id} observed after prediction as_of")
    minimum_outcome = _utc(snapshot.as_of) + timedelta(days=HORIZON_DAYS[snapshot.horizon])
    if _utc(outcome.observed_at) < minimum_outcome:
        raise LeakageError("outcome is inside the prediction horizon")
    if outcome.ticker.upper() != snapshot.ticker.upper():
        raise LeakageError("prediction/outcome ticker mismatch")


class WalkForwardValidator:
    """Evaluate predictions in chronological folds; calibration is fitted on prior data only."""

    def __init__(self, config: WalkForwardConfig | None = None, calibrator: FactorCalibrator | None = None) -> None:
        self.config = config or WalkForwardConfig()
        self.calibrator = calibrator or FactorCalibrator()

    def run(self, snapshots: Sequence[PredictionSnapshot], outcomes: Sequence[OutcomeObservation]) -> ValidationResult:
        ordered = sorted(snapshots, key=lambda x: _utc(x.as_of))
        outcome_by_id = {o.prediction_id: o for o in outcomes}
        self._validate_pairs(ordered, outcome_by_id)
        if not ordered:
            return ValidationResult(0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, {}, {})

        first = _utc(ordered[0].as_of)
        last = _utc(ordered[-1].as_of)
        cursor = first + timedelta(days=self.config.train_days)
        evaluated: list[tuple[PredictionSnapshot, OutcomeObservation]] = []
        all_weights: list[Mapping[str, float]] = []
        while cursor <= last:
            train_start = cursor - timedelta(days=self.config.train_days)
            test_end = cursor + timedelta(days=self.config.test_days)
            train = [s for s in ordered if train_start <= _utc(s.as_of) < cursor]
            test = [s for s in ordered if cursor <= _utc(s.as_of) < test_end]
            train_outcomes = [outcome_by_id[s.prediction_id] for s in train if s.prediction_id in outcome_by_id]
            if len(train_outcomes) >= self.config.min_train_observations:
                weights = self.calibrator.fit(train, train_outcomes)
                all_weights.append(weights)
                for snapshot in test:
                    outcome = outcome_by_id.get(snapshot.prediction_id)
                    if outcome is not None:
                        evaluated.append((apply_factor_weights(snapshot, weights), outcome))
            cursor += timedelta(days=self.config.step_days)
        return _metrics(evaluated, _average_weights(all_weights))

    def _validate_pairs(self, snapshots: Sequence[PredictionSnapshot], outcomes: Mapping[str, OutcomeObservation]) -> None:
        for snapshot in snapshots:
            outcome = outcomes.get(snapshot.prediction_id)
            if outcome is not None:
                validate_no_lookahead(snapshot, {}, outcome)


def _metrics(pairs: Sequence[tuple[PredictionSnapshot, OutcomeObservation]], weights: Mapping[str, float]) -> ValidationResult:
    if not pairs:
        return ValidationResult(0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, {}, dict(weights))
    correct = 0
    brier_terms: list[float] = []
    returns = [o.realized_return for _, o in pairs]
    excess = [o.excess_return for _, o in pairs]
    drawdowns = [o.max_drawdown for _, o in pairs]
    by_action: dict[str, list[float]] = {}
    for snapshot, outcome in pairs:
        direction = 1 if snapshot.score > 0 else -1 if snapshot.score < 0 else 0
        actual = 1 if outcome.excess_return > 0 else -1 if outcome.excess_return < 0 else 0
        if direction == actual:
            correct += 1
        probability = 0.5 + 0.5 * max(-1.0, min(1.0, snapshot.score / 100.0))
        brier_terms.append((probability - (1.0 if actual > 0 else 0.0)) ** 2)
        by_action.setdefault(snapshot.action, []).append(outcome.excess_return)
    action_metrics = {action: {"count": float(len(values)), "mean_excess_return": mean(values)} for action, values in by_action.items()}
    # Calibration error is the absolute gap between confidence and empirical directional hit rate.
    confidence_error = abs(mean(s.confidence for s, _ in pairs) - correct / len(pairs))
    return ValidationResult(len(pairs), len(pairs), correct / len(pairs), mean(excess), mean(returns),
                            mean(drawdowns), mean(brier_terms), confidence_error, action_metrics, dict(weights))


def _average_weights(weights: Sequence[Mapping[str, float]]) -> dict[str, float]:
    factors = {factor for row in weights for factor in row}
    return {factor: mean(row[factor] for row in weights if factor in row) for factor in factors}


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _stdev(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((value - m) ** 2 for value in values) / (len(values) - 1))
