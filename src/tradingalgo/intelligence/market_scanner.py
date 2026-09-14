"""Market-wide discovery for advisory requests without explicit tickers.

Discovery is intentionally separate from full security analysis: a configured
provider supplies a point-in-time candidate universe, the scanner ranks that
universe using transparent horizon-specific factors, and only the shortlist is
sent to the normal evidence-backed orchestrator.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from ..data.health import ProviderHealthRegistry
from ..data.providers import ProviderResponse
from .discovery_scoring import DiscoveryPolicy, passes_filters, score_row


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
        horizon: str = "short",
        min_evidence: int = 0,
    ) -> DiscoveryResult:
        point_in_time = as_of or datetime.now(timezone.utc)
        if point_in_time.tzinfo is None:
            point_in_time = point_in_time.replace(tzinfo=timezone.utc)
        else:
            point_in_time = point_in_time.astimezone(timezone.utc)

        if limit < 1:
            raise ValueError("limit must be at least 1")
        if horizon.strip().lower() not in {"short", "long"}:
            raise ValueError("horizon must be short or long")
        if min_evidence < 0:
            raise ValueError("min_evidence cannot be negative")

        if not self.health.get(provider).available:
            return DiscoveryResult((), None, {provider: "provider health gate is open"}, point_in_time)

        try:
            response = fetch()
            self.health.record_success(provider)
        except Exception as exc:
            self.health.record_failure(provider)
            return DiscoveryResult((), None, {provider: str(exc)}, point_in_time)

        policy = DiscoveryPolicy(horizon=horizon, min_evidence=min_evidence)
        candidates: list[MarketCandidate] = []
        for row in _rows(response.payload):
            candidate = _candidate(row, provider, market, policy)
            if candidate is not None:
                candidates.append(candidate)

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


def _candidate(row: dict[str, Any], provider: str, default_market: str, policy: DiscoveryPolicy) -> MarketCandidate | None:
    ticker = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
    if not ticker:
        return None

    accepted, filter_reasons = passes_filters(row, policy)
    # Legacy catalog rows may not carry price/volume/evidence metadata. Do not
    # manufacture those values; the full-analysis evidence gate remains the
    # final publication gate in the recommendation service.
    if policy.min_evidence > 0 and "minimum evidence filter" in filter_reasons:
        return None
    if not accepted and filter_reasons:
        return None

    supplied_score = row.get("score")
    if supplied_score is not None:
        try:
            score = float(supplied_score)
        except (TypeError, ValueError):
            score, factors = score_row(row, policy)
        else:
            _, factors = score_row(row, policy)
    else:
        score, factors = score_row(row, policy)

    rationale = str(row.get("rationale") or row.get("reason") or _rationale(policy, factors))
    return MarketCandidate(
        ticker=ticker,
        market=str(row.get("market") or default_market),
        name=str(row.get("name")) if row.get("name") else None,
        score=max(-100.0, min(100.0, score)),
        rationale=rationale,
        factors=factors,
        source=provider,
    )


def _rationale(policy: DiscoveryPolicy, factors: dict[str, float]) -> str:
    ranked = sorted(factors.items(), key=lambda item: item[1], reverse=True)
    leaders = ", ".join(f"{name}={value:.0f}" for name, value in ranked[:3])
    return f"{policy.horizon.title()}-term factor model; strongest factors: {leaders}."
