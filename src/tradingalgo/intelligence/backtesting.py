"""Leakage-safe event-free backtesting primitives for the advisory system."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Sequence

from ..data.candles import Candle
from .learning import PredictionSnapshot, statistical_tests
from .outcomes import PriceOutcome, realize_price_outcome


@dataclass(frozen=True)
class BacktestConfig:
    warmup_sessions: int = 200
    rebalance_every_sessions: int = 1
    allow_overlapping_positions: bool = False
    benchmark_required: bool = False
    transaction_cost_bps: float = 10.0

    def __post_init__(self) -> None:
        if self.warmup_sessions < 0 or self.rebalance_every_sessions < 1 or self.transaction_cost_bps < 0:
            raise ValueError("invalid backtest configuration")


@dataclass(frozen=True)
class BacktestTrade:
    prediction: PredictionSnapshot
    outcome: PriceOutcome
    net_return: float


@dataclass(frozen=True)
class BacktestReport:
    ticker: str
    observations: int
    trades: int
    mean_return: float
    mean_excess_return: float
    hit_rate: float
    cumulative_return: float
    max_drawdown: float
    average_adverse_excursion: float
    average_favorable_excursion: float
    statistical_test: object
    skipped: int


Predictor = Callable[[date, Sequence[Candle]], PredictionSnapshot | None]


def run_backtest(
    ticker: str,
    candles: Sequence[Candle],
    predictor: Predictor,
    *,
    benchmark_candles: Sequence[Candle] | None = None,
    config: BacktestConfig | None = None,
) -> BacktestReport:
    """Replay candles chronologically; predictor receives only data through as_of."""
    cfg = config or BacktestConfig()
    ordered = sorted((c for c in candles if c.ticker.upper() == ticker.upper()), key=lambda c: c.session)
    if len(ordered) <= cfg.warmup_sessions:
        return _empty(ticker)
    trades: list[BacktestTrade] = []
    last_prediction_index = -cfg.rebalance_every_sessions
    active_until: date | None = None
    skipped = 0
    for index in range(cfg.warmup_sessions, len(ordered)):
        if index - last_prediction_index < cfg.rebalance_every_sessions:
            continue
        as_of = ordered[index].session
        if not cfg.allow_overlapping_positions and active_until is not None and as_of <= active_until:
            skipped += 1
            continue
        prefix = ordered[: index + 1]
        prediction = predictor(as_of, prefix)
        last_prediction_index = index
        if prediction is None or prediction.ticker.upper() != ticker.upper() or prediction.as_of.date() > as_of:
            skipped += 1
            continue
        try:
            outcome = realize_price_outcome(prediction, ordered, benchmark_candles)
        except (ValueError, KeyError):
            skipped += 1
            continue
        active_until = outcome.exit_session
        gross = outcome.observation.realized_return
        cost = (2.0 * cfg.transaction_cost_bps) / 10000.0
        trades.append(BacktestTrade(prediction, outcome, gross - cost))
    return _report(ticker, trades, skipped)


def _report(ticker: str, trades: Sequence[BacktestTrade], skipped: int) -> BacktestReport:
    if not trades:
        return _empty(ticker, skipped)
    returns = [t.net_return for t in trades]
    excess = [t.outcome.observation.excess_return for t in trades]
    wins = sum(value > 0 for value in returns)
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for value in returns:
        equity *= 1.0 + value
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)
    pairs = [(t.prediction, t.outcome.observation) for t in trades]
    return BacktestReport(
        ticker=ticker.upper(), observations=len(trades), trades=len(trades),
        mean_return=sum(returns) / len(returns), mean_excess_return=sum(excess) / len(excess),
        hit_rate=wins / len(returns), cumulative_return=equity - 1.0, max_drawdown=max_dd,
        average_adverse_excursion=sum(t.outcome.maximum_adverse_excursion for t in trades) / len(trades),
        average_favorable_excursion=sum(t.outcome.maximum_favorable_excursion for t in trades) / len(trades),
        statistical_test=statistical_tests(pairs), skipped=max(0, skipped),
    )


def _empty(ticker: str, skipped: int = 0) -> BacktestReport:
    return BacktestReport(ticker.upper(), 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, statistical_tests([]), skipped)
