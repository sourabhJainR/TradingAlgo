"""Leakage-safe realized price outcomes for historical advisory predictions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Sequence

from ..data.candles import Candle
from .learning import HORIZON_DAYS, OutcomeObservation, PredictionSnapshot


class OutcomeUnavailable(ValueError):
    """Raised when the supplied historical prices do not cover the horizon."""


@dataclass(frozen=True)
class PriceOutcome:
    observation: OutcomeObservation
    entry_session: date
    exit_session: date
    entry_price: float
    exit_price: float
    maximum_adverse_excursion: float
    maximum_favorable_excursion: float


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _direction(snapshot: PredictionSnapshot) -> int:
    if snapshot.action.upper() in {"BUY", "STRONG BUY"} or snapshot.score > 0:
        return 1
    if snapshot.action.upper() in {"AVOID", "SELL", "STRONG SELL"} or snapshot.score < 0:
        return -1
    return 0


def _price_return(entry: float, exit_: float, direction: int) -> float:
    if entry <= 0 or direction == 0:
        return 0.0
    return direction * (exit_ / entry - 1.0)


def realize_price_outcome(
    snapshot: PredictionSnapshot,
    candles: Sequence[Candle],
    benchmark_candles: Sequence[Candle] | None = None,
) -> PriceOutcome:
    """Realize one prediction using only sessions strictly after its as-of date.

    Entry is the first available session after the prediction timestamp at its open.
    Exit is the first available session on/after the calendar horizon date. MAE/MFE
    are measured over the observed path from entry through exit. This avoids using a
    daily close that was not yet known at prediction time.
    """
    ordered = sorted((c for c in candles if c.ticker.upper() == snapshot.ticker.upper()), key=lambda c: c.session)
    start_date = _utc(snapshot.as_of).date()
    entry_candidates = [c for c in ordered if c.session > start_date]
    target_date = start_date + timedelta(days=HORIZON_DAYS[snapshot.horizon])
    exit_candidates = [c for c in entry_candidates if c.session >= target_date]
    if not entry_candidates or not exit_candidates:
        raise OutcomeUnavailable(f"insufficient {snapshot.horizon.value} price history for {snapshot.prediction_id}")

    entry = entry_candidates[0]
    exit_ = exit_candidates[0]
    path = [c for c in entry_candidates if c.session <= exit_.session]
    direction = _direction(snapshot)
    realized = _price_return(entry.open, exit_.close, direction)

    if direction == 1:
        mae = min((c.low / entry.open - 1.0 for c in path), default=0.0)
        mfe = max((c.high / entry.open - 1.0 for c in path), default=0.0)
    elif direction == -1:
        mae = min((entry.open / c.high - 1.0 for c in path), default=0.0)
        mfe = max((entry.open / c.low - 1.0 for c in path), default=0.0)
    else:
        mae = mfe = 0.0

    benchmark_return = 0.0
    if benchmark_candles:
        bench = sorted(benchmark_candles, key=lambda c: c.session)
        b_entries = [c for c in bench if c.session >= entry.session]
        b_exits = [c for c in b_entries if c.session >= exit_.session]
        if b_entries and b_exits and b_entries[0].open > 0:
            benchmark_return = b_exits[0].close / b_entries[0].open - 1.0

    observation = OutcomeObservation(
        prediction_id=snapshot.prediction_id,
        ticker=snapshot.ticker,
        observed_at=datetime.combine(exit_.session, datetime.min.time(), tzinfo=timezone.utc),
        realized_return=realized,
        benchmark_return=benchmark_return,
        max_drawdown=mae,
        maximum_adverse_excursion=mae,
        maximum_favorable_excursion=mfe,
    )
    return PriceOutcome(observation, entry.session, exit_.session, entry.open, exit_.close, mae, mfe)
