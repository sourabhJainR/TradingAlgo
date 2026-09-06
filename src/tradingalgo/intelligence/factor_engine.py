"""Derived fundamental and valuation factors from point-in-time evidence.

The engine never invents missing values. Growth/margin trends require multiple
reported periods and are calculated only from facts whose filing timestamp is
known to be available at the requested as-of time.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Iterable

from .models import Evidence, Horizon, Signal, SourceType


@dataclass(frozen=True)
class FactorSnapshot:
    quality_score: float
    growth_score: float
    valuation_score: float
    evidence_ids: tuple[str, ...]
    features: dict[str, float]


def _clip(value: float) -> float:
    return max(-100.0, min(100.0, value))


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _facts(evidence: Iterable[Evidence], as_of: datetime | None) -> dict[str, list[Evidence]]:
    cutoff = _utc(as_of) if as_of else None
    result: dict[str, list[Evidence]] = {}
    for item in evidence:
        if item.source_type not in (SourceType.SEC_FILING, SourceType.FUNDAMENTAL):
            continue
        available = item.published_at or item.observed_at
        if cutoff and _utc(available) > cutoff:
            continue
        concept = str(item.facts.get("concept") or "")
        if concept:
            result.setdefault(concept, []).append(item)
    for rows in result.values():
        rows.sort(key=lambda x: str(x.facts.get("period_end") or ""))
    return result


def build_fundamental_factors(ticker: str, evidence: Iterable[Evidence], *, as_of: datetime | None = None,
                              horizon: Horizon = Horizon.MEDIUM) -> tuple[Signal, ...]:
    grouped = _facts(evidence, as_of)
    revenue = grouped.get("Revenue", []) + grouped.get("Revenues", []) + grouped.get("SalesRevenueNet", [])
    income = grouped.get("NetIncomeLoss", [])
    assets = grouped.get("Assets", [])
    debt = grouped.get("LongTermDebtNoncurrent", [])
    cash = grouped.get("CashAndCashEquivalentsAtCarryingValue", [])
    ids = tuple(dict.fromkeys(item.id for rows in grouped.values() for item in rows[-3:]))

    growth = _growth(revenue)
    margin = _margin(income, revenue)
    balance = _balance(debt, cash, assets)
    quality = _clip(0.55 * _score_positive(growth) + 0.45 * _score_positive(balance))
    growth_score = _clip(_score_positive(growth))
    quality_score = _clip(0.65 * _score_positive(margin) + 0.35 * _score_positive(balance))

    signals: list[Signal] = []
    if revenue or income or assets or debt or cash:
        confidence = min(0.92, 0.45 + 0.08 * sum(bool(x) for x in (revenue, income, assets, debt, cash)))
        signals.append(Signal(name="fundamental_quality", category="fundamental", ticker=ticker.upper(),
            score=quality_score, confidence=confidence, horizon=horizon,
            rationale=f"Quality combines profitability trend and balance-sheet resilience; margin={margin:.3f}, balance={balance:.3f}.",
            evidence_ids=list(ids), features={"profit_margin": margin, "balance_score": balance, "revenue_growth": growth}))
        signals.append(Signal(name="fundamental_growth", category="growth", ticker=ticker.upper(),
            score=growth_score, confidence=confidence, horizon=horizon,
            rationale=f"Revenue growth evidence supports a {('positive' if growth > 0 else 'negative' if growth < 0 else 'neutral')} growth trend.",
            evidence_ids=list(x.id for x in revenue[-3:]), features={"revenue_growth": growth}))
    return tuple(signals)


def build_valuation_signal(ticker: str, evidence: Iterable[Evidence], *, as_of: datetime | None = None,
                           horizon: Horizon = Horizon.MEDIUM) -> Signal | None:
    grouped = _facts(evidence, as_of)
    # Valuation is intentionally conservative until market-cap/price/EV facts are available.
    valuation_rows = grouped.get("MarketCapitalization", []) + grouped.get("EnterpriseValue", [])
    if not valuation_rows:
        return None
    ids = [x.id for x in valuation_rows[-3:]]
    values = [float(x.facts.get("value", 0.0)) for x in valuation_rows[-3:] if x.facts.get("value") is not None]
    if not values or values[-1] <= 0:
        return None
    return Signal(name="valuation_context", category="valuation", ticker=ticker.upper(), score=0.0,
        confidence=0.35, horizon=horizon,
        rationale="Valuation data is present but no comparable earnings/cash-flow or peer multiple is available; no valuation direction is fabricated.",
        evidence_ids=ids, features={"latest_enterprise_or_market_value": values[-1]})


def _growth(rows: list[Evidence]) -> float:
    values = [float(x.facts["value"]) for x in rows if x.facts.get("value") is not None]
    if len(values) < 2 or values[-2] == 0:
        return 0.0
    return (values[-1] / values[-2]) - 1.0


def _margin(income: list[Evidence], revenue: list[Evidence]) -> float:
    if not income or not revenue:
        return 0.0
    revenue_by_period = {str(x.facts.get("period_end")): float(x.facts["value"]) for x in revenue if x.facts.get("value")}
    margins = [float(x.facts["value"]) / revenue_by_period[str(x.facts.get("period_end"))]
               for x in income if str(x.facts.get("period_end")) in revenue_by_period and revenue_by_period[str(x.facts.get("period_end"))] != 0]
    return margins[-1] if margins else 0.0


def _balance(debt: list[Evidence], cash: list[Evidence], assets: list[Evidence]) -> float:
    if not assets:
        return 0.0
    a = float(assets[-1].facts.get("value", 0.0))
    d = float(debt[-1].facts.get("value", 0.0)) if debt else 0.0
    c = float(cash[-1].facts.get("value", 0.0)) if cash else 0.0
    if a == 0:
        return 0.0
    return (c - d) / a


def _score_positive(value: float) -> float:
    if value == 0:
        return 0.0
    return _clip(value * 100.0)
