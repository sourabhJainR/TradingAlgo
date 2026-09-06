from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .models import Evidence, Horizon, Polarity, SourceType


@dataclass(frozen=True)
class MacroObservation:
    series_id: str
    value: float
    observation_date: str


def normalize_fred(series_id: str, payload: dict[str, Any]) -> list[MacroObservation]:
    rows = payload.get("observations", [])
    result: list[MacroObservation] = []
    for row in rows:
        try:
            value = float(row["value"])
        except (KeyError, TypeError, ValueError):
            continue
        if value != value:
            continue
        result.append(MacroObservation(series_id, value, str(row.get("date", ""))))
    return result


def macro_evidence(ticker: str, observation: MacroObservation, baseline: float | None = None) -> Evidence:
    delta = 0.0 if baseline is None else observation.value - baseline
    polarity = Polarity.BULLISH if delta > 0 else Polarity.BEARISH if delta < 0 else Polarity.NEUTRAL
    return Evidence(id=f"fred:{observation.series_id}:{observation.observation_date}:{ticker.upper()}",
        ticker=ticker.upper(), source_type=SourceType.MACRO, source_name="fred",
        observed_at=datetime.now(timezone.utc), published_at=datetime.now(timezone.utc),
        title=f"Macro observation {observation.series_id}",
        summary=f"{observation.series_id}={observation.value}; delta={delta}",
        polarity=polarity, severity=max(-1.0, min(1.0, delta)), confidence=.8, novelty=.5,
        horizon=Horizon.MEDIUM, tags=["macro", observation.series_id],
        facts={"value": observation.value, "baseline": baseline, "delta": delta})
