from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FinancialFact:
    ticker: str
    concept: str
    value: float
    unit: str
    period_end: str
    filing_date: str | None
    form: str | None
    accession: str | None


def _latest_units(concept: dict[str, Any], preferred: tuple[str, ...]) -> tuple[str, list[dict[str, Any]]] | None:
    units = concept.get("units", {})
    for unit in preferred:
        if unit in units and units[unit]:
            return unit, units[unit]
    return next(iter(units.items()), None)


def normalize_companyfacts(ticker: str, payload: dict[str, Any]) -> list[FinancialFact]:
    facts = payload.get("facts", {})
    result: list[FinancialFact] = []
    preferred = {
        "Revenue": ("USD",),
        "Revenues": ("USD",),
        "SalesRevenueNet": ("USD",),
        "NetIncomeLoss": ("USD",),
        "Assets": ("USD",),
        "Liabilities": ("USD",),
        "StockholdersEquity": ("USD",),
        "CashAndCashEquivalentsAtCarryingValue": ("USD",),
        "LongTermDebtNoncurrent": ("USD",),
        "EarningsPerShareDiluted": ("USD/shares", "USD/shares"),
    }
    for namespace in ("us-gaap", "dei"):
        for concept_name, concept in facts.get(namespace, {}).items():
            selected = _latest_units(concept, preferred.get(concept_name, ("USD", "shares", "pure")))
            if not selected:
                continue
            unit, rows = selected
            valid = [r for r in rows if r.get("val") is not None and r.get("end")]
            if not valid:
                continue
            row = valid[-1]
            try:
                value = float(row["val"])
            except (TypeError, ValueError):
                continue
            result.append(FinancialFact(ticker=ticker.upper(), concept=concept_name, value=value, unit=unit,
                period_end=str(row["end"]), filing_date=row.get("filed"), form=row.get("form"), accession=row.get("accn")))
    return result
