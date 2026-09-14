"""Transparent scoring and guardrails for market-wide candidate discovery."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DiscoveryPolicy:
    """Controls discovery quality before full stock analysis."""

    horizon: str = "short"
    min_price: float = 5.0
    max_price: float = 10_000.0
    min_avg_volume: float = 100_000.0
    min_dollar_volume: float = 2_000_000.0
    min_evidence: int = 3
    min_score: float = 35.0


SHORT_WEIGHTS = {
    "momentum": 0.24,
    "trend": 0.20,
    "relative_strength": 0.16,
    "liquidity": 0.12,
    "catalyst": 0.10,
    "fundamentals": 0.05,
    "regime": 0.08,
    "risk": 0.05,
}

LONG_WEIGHTS = {
    "momentum": 0.08,
    "trend": 0.18,
    "relative_strength": 0.12,
    "liquidity": 0.08,
    "catalyst": 0.05,
    "fundamentals": 0.30,
    "regime": 0.10,
    "risk": 0.09,
}


def _number(row: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            try:
                return float(str(value).replace(",", "").replace("%", ""))
            except (TypeError, ValueError):
                continue
    return default


def _evidence_count(row: dict[str, Any]) -> int:
    explicit = row.get("evidence_count")
    if explicit not in (None, ""):
        try:
            return max(0, int(explicit))
        except (TypeError, ValueError):
            pass
    fields = (
        ("price", "last_price"),
        ("volume", "avg_volume", "average_volume"),
        ("momentum", "return_20d", "change_percentage"),
        ("trend", "trend_score"),
        ("fundamentals", "fundamental_score"),
        ("sector_relative_strength", "relative_strength"),
        ("regime", "market_regime"),
    )
    return sum(any(row.get(key) not in (None, "") for key in keys) for keys in fields)


def passes_filters(row: dict[str, Any], policy: DiscoveryPolicy) -> tuple[bool, list[str]]:
    """Apply hard quality filters only when the provider supplies the inputs."""
    reasons: list[str] = []
    price = _number(row, "price", "last_price")
    avg_volume = _number(row, "avg_volume", "average_volume", "volume")
    dollar_volume = _number(row, "dollar_volume", "avg_dollar_volume")
    evidence = _evidence_count(row)

    if price and not (policy.min_price <= price <= policy.max_price):
        reasons.append("price filter")
    if avg_volume and avg_volume < policy.min_avg_volume:
        reasons.append("liquidity filter")
    if dollar_volume and dollar_volume < policy.min_dollar_volume:
        reasons.append("dollar-volume filter")
    if evidence < policy.min_evidence:
        reasons.append("minimum evidence filter")

    # If price/volume are absent, evidence remains the controlling gate rather
    # than inventing liquidity data from a provider catalog.
    return not reasons, reasons


def score_row(row: dict[str, Any], policy: DiscoveryPolicy) -> tuple[float, dict[str, float]]:
    """Score a candidate with separate short- and long-horizon factor weights."""
    factors = {
        "momentum": _number(row, "momentum", "return_20d", "change_percentage"),
        "trend": _number(row, "trend", "trend_score"),
        "relative_strength": _number(row, "sector_relative_strength", "relative_strength"),
        "liquidity": _number(row, "liquidity", "liquidity_score"),
        "catalyst": _number(row, "catalyst", "catalyst_score"),
        "fundamentals": _number(row, "fundamentals", "fundamental_score"),
        "regime": _number(row, "market_regime", "regime_score", default=50.0),
        "risk": _number(row, "risk", "risk_score"),
    }
    # Percent-return inputs are converted to the model's 0-100 factor scale.
    for key in ("momentum", "relative_strength"):
        if abs(factors[key]) <= 20:
            factors[key] = max(0.0, min(100.0, 50.0 + factors[key] * 2.5))
    weights = SHORT_WEIGHTS if policy.horizon.lower() == "short" else LONG_WEIGHTS
    score = sum(factors[key] * weight for key, weight in weights.items())
    return max(0.0, min(100.0, score)), factors


def rank_rows(rows: list[dict[str, Any]], policy: DiscoveryPolicy) -> list[tuple[dict[str, Any], float, dict[str, float], list[str]]]:
    ranked: list[tuple[dict[str, Any], float, dict[str, float], list[str]]] = []
    for row in rows:
        accepted, reasons = passes_filters(row, policy)
        score, factors = score_row(row, policy)
        if accepted and score >= policy.min_score:
            ranked.append((row, score, factors, []))
        elif not accepted:
            ranked.append((row, score, factors, reasons))
    ranked.sort(key=lambda item: (item[1], str(item[0].get("ticker") or item[0].get("symbol") or "")), reverse=True)
    return ranked
