"""Market-wide discovery for advisory requests without explicit tickers.

Discovery is intentionally separate from full security analysis: a configured
provider supplies a point-in-time candidate universe, the scanner ranks that
universe using transparent pre-screen factors, and only the shortlist is sent
to the normal evidence-backed orchestrator.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from ..data.health import ProviderHealthRegistry
from ..data.providers import ProviderResponse


@dataclass(frozen=True)
class MarketCandidate:
    ticker: str
    market: str
    name: str | None
    score: float
    rationale: str
    factors: dict[str, float]
    source: str


@dataclass(frozen=True)
class DiscoveryResult:
    candidates: tuple[MarketCandidate, ...]
    provider: str | None
    errors: dict[str, str]
    as_of: datetime


@dataclass(frozen=True)
class MarketDiscovery:
    """Rank a provider-supplied market universe without inventing data."""

    health: ProviderHealthRegistry

    def discover(
        self,
        fetch: Callable[[], ProviderResponse],
        *,
        provider: str = "market-universe",
        market: str = "global",
        limit: int = 10,
        as_of: datetime | None = None,
    ) -> DiscoveryResult:
        point_in_time = as_of or datetime.now(timezone.utc)
        if point_in_time.tzinfo is None:
            point_in_time = point_in_time.replace(tzinfo=timezone.utc)
        else:
            point_in_time = point_in_time.astimezone(timezone.utc)

        if limit < 1:
            raise ValueError("limit must be at least 1")

        if not self.health.get(provider).available:
            return DiscoveryResult((), None, {provider: "provider health gate is open"}, point_in_time)

        try:
            response = fetch()
            self.health.record_success(provider)
        except Exception as exc:
            self.health.record_failure(provider)
            return DiscoveryResult((), None, {provider: str(exc)}, point_in_time)

        candidates = [
            candidate
            for row in _rows(response.payload)
            if (candidate := _candidate(row, provider, market)) is not None
        ]
        candidates.sort(key=lambda item: (item.score, item.ticker), reverse=True)
        return DiscoveryResult(tuple(candidates[:limit]), provider, {}, point_in_time)


def _rows(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, list):
        return (row for row in payload if isinstance(row, dict))
    if isinstance(payload, dict):
        for key in ("candidates", "stocks", "symbols", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return (row for row in value if isinstance(row, dict))
    return ()


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _candidate(row: dict[str, Any], provider: str, default_market: str) -> MarketCandidate | None:
    ticker = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
    if not ticker:
        return None

    factors = {
        "momentum": _number(row.get("momentum"), _number(row.get("relative_strength"))),
        "trend": _number(row.get("trend"), _number(row.get("trend_score"))),
        "fundamentals": _number(row.get("fundamentals"), _number(row.get("fundamental_score"))),
        "catalyst": _number(row.get("catalyst"), _number(row.get("catalyst_score"))),
        "liquidity": _number(row.get("liquidity"), _number(row.get("liquidity_score"))),
        "risk": _number(row.get("risk"), _number(row.get("risk_score"))),
    }
    supplied_score = row.get("score")
    if supplied_score is not None:
        score = _number(supplied_score)
    else:
        score = (
            factors["momentum"] * 0.25
            + factors["trend"] * 0.20
            + factors["fundamentals"] * 0.20
            + factors["catalyst"] * 0.15
            + factors["liquidity"] * 0.10
            - factors["risk"] * 0.10
        )

    rationale = str(row.get("rationale") or row.get("reason") or "Ranked by configured market-screen factors.")
    return MarketCandidate(
        ticker=ticker,
        market=str(row.get("market") or default_market),
        name=str(row.get("name")) if row.get("name") else None,
        score=max(-100.0, min(100.0, score)),
        rationale=rationale,
        factors=factors,
        source=provider,
    )
