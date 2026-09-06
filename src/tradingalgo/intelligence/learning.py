"""Historical prediction tracking, leakage-safe validation and statistical testing."""
from __future__ import annotations

import hashlib
import json
import math
import random
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Mapping, Sequence

from .models import Advisory, Horizon

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
        return cls(prediction_id, advisory.ticker.upper(), timestamp, advisory.action, advisory.score,
                   advisory.confidence, advisory.horizon,
                   tuple(dict.fromkeys(e for s in advisory.signals for e in s.evidence_ids)), factors)


def prediction_id_for(advisory: Advisory, as_of: datetime) -> str:
    """Create a reproducible identity for the exact advisory/as-of snapshot."""
    payload = {
        "ticker": advisory.ticker.upper(), "as_of": _utc(as_of).isoformat(),
        "action": advisory.action, "score": advisory.score, "confidence": advisory.confidence,
        "horizon": advisory.horizon.value,
        "signals": [(s.name, s.category, s.score, s.confidence, sorted(s.evidence_ids)) for s in advisory.signals],
    }
    return "pred-" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]


@dataclass(frozen=True)
class OutcomeObservation:
    prediction_id: str
    ticker: str
    observed_at: datetime
    realized_return: float
    benchmark_return: float = 0.0
    max_drawdown: float = 0.0
    maximum_adverse_excursion: float = 0.0
    maximum_favorable_excursion: float = 0.0

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
class StatisticalTestResult:
    sample_size: int
    mean_excess_return: float
    baseline_mean: float
    improvement: float
    t_statistic: float
    p_value: float
    bootstrap_ci_low: float
    bootstrap_ci_high: float
    permutation_p_value: float


@dataclass(frozen=True)
class WalkForwardConfig:
    train_days: int = 365
    test_days: int = 90
    step_days: int = 30
    embargo_days: int = 0
    min_train_observations: int = 20
    min_factor_observations: int = 20
    significance_alpha: float = 0.05
    bootstrap_samples: int = 1000
    permutation_samples: int = 1000


class LearningStore:
    """Small durable SQLite store for exact predictions and realized outcomes."""

    def __init__(self, path: str | Path = "data/tradingalgo_learning.sqlite") -> None:
        self.path = str(path); Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.execute("CREATE TABLE IF NOT EXISTS predictions (prediction_id TEXT PRIMARY KEY, ticker TEXT NOT NULL, as_of TEXT NOT NULL, action TEXT NOT NULL, score REAL NOT NULL, confidence REAL NOT NULL, horizon TEXT NOT NULL, evidence_ids TEXT NOT NULL, factor_scores TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS outcomes (prediction_id TEXT PRIMARY KEY, ticker TEXT NOT NULL, observed_at TEXT NOT NULL, realized_return REAL NOT NULL, benchmark_return REAL NOT NULL, max_drawdown REAL NOT NULL, maximum_adverse_excursion REAL NOT NULL DEFAULT 0, maximum_favorable_excursion REAL NOT NULL DEFAULT 0, FOREIGN KEY(prediction_id) REFERENCES predictions(prediction_id))")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_predictions_time ON predictions(as_of, ticker)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_time ON outcomes(observed_at, ticker)")
        self.db.commit()

    def save_prediction(self, snapshot: PredictionSnapshot) -> None:
        self.db.execute("INSERT OR REPLACE INTO predictions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (snapshot.prediction_id, snapshot.ticker, _utc(snapshot.as_of).isoformat(), snapshot.action,
             snapshot.score, snapshot.confidence, snapshot.horizon.value, json.dumps(snapshot.evidence_ids),
             json.dumps(dict(snapshot.factor_scores), sort_keys=True)))
        self.db.commit()

    def save_outcome(self, outcome: OutcomeObservation) -> None:
        self.db.execute("INSERT OR REPLACE INTO outcomes VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (outcome.prediction_id, outcome.ticker, _utc(outcome.observed_at).isoformat(), outcome.realized_return,
             outcome.benchmark_return, outcome.max_drawdown, outcome.maximum_adverse_excursion,
             outcome.maximum_favorable_excursion))
        self.db.commit()

    def close(self) -> None:
        self.db.close()


class FactorCalibrator:
    """Regularized factor calibration using only prior observations."""
    def __init__(self, min_weight: float = .50, max_weight: float = 1.50, strength: float = .50,
                 min_observations: int = 20) -> None:
        if min_weight <= 0 or max_weight < min_weight or strength < 0 or min_observations < 3:
            raise ValueError("invalid calibration bounds")
        self.min_weight, self.max_weight, self.strength, self.min_observations = min_weight, max_weight, strength, min_observations

    def fit(self, snapshots: Sequence[PredictionSnapshot], outcomes: Sequence[OutcomeObservation]) -> dict[str, float]:
        by_id = {o.prediction_id: o for o in outcomes}; pairs: dict[str, list[tuple[float, float]]] = {}
        for snapshot in snapshots:
            outcome = by_id.get(snapshot.prediction_id)
            if outcome is None or _utc(outcome.observed_at) <= _utc(snapshot.as_of): continue
            for factor, value in snapshot.factor_scores.items(): pairs.setdefault(factor, []).append((float(value), outcome.excess_return))
        raw = {f: self._weight(v) for f, v in pairs.items() if len(v) >= self.min_observations}
        if not raw: return {}
        center = mean(raw.values()) or 1.0
        return {f: max(self.min_weight, min(self.max_weight, w / center)) for f, w in raw.items()}

    def _weight(self, pairs: Sequence[tuple[float, float]]) -> float:
        xs, ys = [x for x, _ in pairs], [y for _, y in pairs]; sx, sy = _stdev(xs), _stdev(ys)
        if sx == 0 or sy == 0: return 1.0
        corr = sum((x - mean(xs)) * (y - mean(ys)) for x, y in pairs) / ((len(pairs) - 1) * sx * sy)
        # Shrink noisy correlations toward zero as sample size falls.
        shrink = len(pairs) / (len(pairs) + 20.0)
        return max(self.min_weight, min(self.max_weight, 1.0 + self.strength * corr * shrink))


def apply_factor_weights(snapshot: PredictionSnapshot, weights: Mapping[str, float]) -> PredictionSnapshot:
    if not weights: return snapshot
    adjusted = {name: score * weights.get(name, 1.0) for name, score in snapshot.factor_scores.items()}
    denominator = sum(abs(weights.get(name, 1.0)) for name in snapshot.factor_scores) or 1.0
    score = max(-100.0, min(100.0, sum(adjusted.values()) / denominator))
    return PredictionSnapshot(snapshot.prediction_id, snapshot.ticker, snapshot.as_of, snapshot.action, score,
                              snapshot.confidence, snapshot.horizon, snapshot.evidence_ids, adjusted)


def validate_no_lookahead(snapshot: PredictionSnapshot, evidence_observed_at: Mapping[str, datetime], outcome: OutcomeObservation) -> None:
    for evidence_id in snapshot.evidence_ids:
        observed = evidence_observed_at.get(evidence_id)
        if observed is not None and _utc(observed) > _utc(snapshot.as_of):
            raise LeakageError(f"evidence {evidence_id} observed after prediction as_of")
    minimum = _utc(snapshot.as_of) + timedelta(days=HORIZON_DAYS[snapshot.horizon])
    if _utc(outcome.observed_at) < minimum: raise LeakageError("outcome is inside the prediction horizon")
    if outcome.ticker.upper() != snapshot.ticker.upper(): raise LeakageError("prediction/outcome ticker mismatch")


class WalkForwardValidator:
    def __init__(self, config: WalkForwardConfig | None = None, calibrator: FactorCalibrator | None = None) -> None:
        self.config = config or WalkForwardConfig(); self.calibrator = calibrator or FactorCalibrator(min_observations=(config.min_factor_observations if config else 20))

    def run(self, snapshots: Sequence[PredictionSnapshot], outcomes: Sequence[OutcomeObservation]) -> ValidationResult:
        ordered = sorted(snapshots, key=lambda x: _utc(x.as_of)); outcome_by_id = {o.prediction_id: o for o in outcomes}
        self._validate_pairs(ordered, outcome_by_id)
        if not ordered: return _empty_result()
        first, last = _utc(ordered[0].as_of), _utc(ordered[-1].as_of); cursor = first + timedelta(days=self.config.train_days)
        evaluated: list[tuple[PredictionSnapshot, OutcomeObservation]] = []; fold_weights: list[Mapping[str, float]] = []
        while cursor <= last:
            train_start = cursor - timedelta(days=self.config.train_days); test_end = cursor + timedelta(days=self.config.test_days)
            train = [s for s in ordered if train_start <= _utc(s.as_of) < cursor]
            test = [s for s in ordered if cursor <= _utc(s.as_of) < test_end]
            train_outcomes = [outcome_by_id[s.prediction_id] for s in train if s.prediction_id in outcome_by_id and _utc(outcome_by_id[s.prediction_id].observed_at) < cursor - timedelta(days=self.config.embargo_days)]
            if len(train_outcomes) >= self.config.min_train_observations:
                weights = self.calibrator.fit(train, train_outcomes); fold_weights.append(weights)
                evaluated.extend((apply_factor_weights(s, weights), outcome_by_id[s.prediction_id]) for s in test if s.prediction_id in outcome_by_id)
            cursor += timedelta(days=self.config.step_days)
        return _metrics(evaluated, _average_weights(fold_weights))

    def _validate_pairs(self, snapshots: Sequence[PredictionSnapshot], outcomes: Mapping[str, OutcomeObservation]) -> None:
        for snapshot in snapshots:
            if (outcome := outcomes.get(snapshot.prediction_id)) is not None: validate_no_lookahead(snapshot, {}, outcome)


def statistical_tests(pairs: Sequence[tuple[PredictionSnapshot, OutcomeObservation]], *, samples: int = 1000, seed: int = 42) -> StatisticalTestResult:
    values = [o.excess_return for _, o in pairs]; n = len(values)
    if not n: return StatisticalTestResult(0, 0., 0., 0., 0., 1., 0., 0., 1.)
    baseline = 0.0; observed = mean(values); sd = _stdev(values); t = observed / (sd / math.sqrt(n)) if sd else 0.0
    p = 2.0 * (1.0 - _normal_cdf(abs(t))) if n > 1 else 1.0
    rng = random.Random(seed); boot = [mean([rng.choice(values) for _ in values]) for _ in range(max(1, samples))]
    boot.sort(); lo, hi = boot[int(.025 * len(boot))], boot[min(len(boot)-1, int(.975 * len(boot)))]
    exceed = sum(abs(mean([rng.choice(values) for _ in values])) >= abs(observed) for _ in range(max(1, samples)))
    return StatisticalTestResult(n, observed, baseline, observed - baseline, t, p, lo, hi, (exceed + 1) / (max(1, samples) + 1))


def baseline_comparison(pairs: Sequence[tuple[PredictionSnapshot, OutcomeObservation]]) -> dict[str, float]:
    """Compare system returns with no-skill, long-only and score-sign baselines."""
    if not pairs: return {"system_mean_excess": 0., "long_only_mean_excess": 0., "directional_hit_rate": 0.}
    system = [o.excess_return for s, o in pairs]
    long_only = [o.realized_return for _, o in pairs]
    hit = [1.0 if (s.score > 0 and o.excess_return > 0) or (s.score < 0 and o.excess_return < 0) else 0.0 for s, o in pairs if s.score != 0]
    return {"system_mean_excess": mean(system), "long_only_mean_excess": mean(long_only), "directional_hit_rate": mean(hit) if hit else 0.}


def _metrics(pairs: Sequence[tuple[PredictionSnapshot, OutcomeObservation]], weights: Mapping[str, float]) -> ValidationResult:
    if not pairs: return _empty_result(weights)
    correct = 0; brier: list[float] = []; returns = [o.realized_return for _, o in pairs]; excess = [o.excess_return for _, o in pairs]; drawdowns = [o.max_drawdown for _, o in pairs]; by_action: dict[str, list[float]] = {}
    for s, o in pairs:
        direction = 1 if s.score > 0 else -1 if s.score < 0 else 0; actual = 1 if o.excess_return > 0 else -1 if o.excess_return < 0 else 0
        correct += direction == actual
        probability = .5 + .5 * max(-1., min(1., s.score / 100.)); brier.append((probability - (1. if actual > 0 else 0.)) ** 2); by_action.setdefault(s.action, []).append(o.excess_return)
    return ValidationResult(len(pairs), len(pairs), correct / len(pairs), mean(excess), mean(returns), mean(drawdowns), mean(brier), abs(mean(s.confidence for s, _ in pairs) - correct / len(pairs)), {a: {"count": float(len(v)), "mean_excess_return": mean(v)} for a, v in by_action.items()}, dict(weights))


def _empty_result(weights: Mapping[str, float] | None = None) -> ValidationResult:
    return ValidationResult(0, 0, 0., 0., 0., 0., 0., 0., {}, dict(weights or {}))


def _average_weights(weights: Sequence[Mapping[str, float]]) -> dict[str, float]:
    factors = {f for row in weights for f in row}; return {f: mean(row[f] for row in weights if f in row) for f in factors}


def _normal_cdf(x: float) -> float: return .5 * (1. + math.erf(x / math.sqrt(2.)))

def _utc(value: datetime) -> datetime: return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)

def _stdev(values: Sequence[float]) -> float:
    if len(values) < 2: return 0.
    m = mean(values); return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))
