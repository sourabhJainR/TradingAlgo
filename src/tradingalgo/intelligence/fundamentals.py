from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


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


def _latest_units(
    concept: dict[str, Any], preferred: tuple[str, ...]
) -> tuple[str, list[dict[str, Any]]] | None:
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
        "EarningsPerShareDiluted": ("USD/shares",),
    }
    for namespace in ("us-gaap", "dei"):
        for concept_name, concept in facts.get(namespace, {}).items():
            selected = _latest_units(
                concept, preferred.get(concept_name, ("USD", "shares", "pure"))
            )
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
            result.append(
                FinancialFact(
                    ticker=ticker.upper(),
                    concept=concept_name,
                    value=value,
                    unit=unit,
                    period_end=str(row["end"]),
                    filing_date=row.get("filed"),
                    form=row.get("form"),
                    accession=row.get("accn"),
                )
            )
    return result


def analyze_fundamentals(ticker: str, market: str) -> dict[str, Any]:
    """Use free public data for ratios and expose only metrics that materially influence the score."""
    symbol = ticker.upper().strip()
    if market.lower() == "india" and "." not in symbol:
        symbol = f"{symbol}.NS"
    modules = "summaryDetail,defaultKeyStatistics,financialData,summaryProfile"
    try:
        with httpx.Client(
            timeout=8.0,
            headers={"User-Agent": "Mozilla/5.0 TradingAlgo/0.2"},
        ) as client:
            crumb = ""
            try:
                client.get("https://fc.yahoo.com/consent")
                crumb_response = client.get(
                    "https://query1.finance.yahoo.com/v1/test/getcrumb"
                )
                if crumb_response.is_success:
                    crumb = crumb_response.text.strip()
            except httpx.HTTPError:
                pass
            params = {
                "modules": modules,
                "formatted": "false",
                "lang": "en-US",
                "region": "US",
                "corsDomain": "finance.yahoo.com",
            }
            if crumb:
                params["crumb"] = crumb
            response = client.get(
                f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}",
                params=params,
            )
            response.raise_for_status()
            result = response.json().get("quoteSummary", {}).get("result") or []
        if not result:
            return _empty("No fundamental data returned")
        raw = result[0]
        detail = raw.get("summaryDetail", {})
        stats = raw.get("defaultKeyStatistics", {})
        financial = raw.get("financialData", {})
        profile = raw.get("summaryProfile", {})

        def val(section: dict[str, Any], key: str) -> float | None:
            item = section.get(key)
            if isinstance(item, dict):
                item = item.get("raw")
            try:
                return float(item) if item is not None else None
            except (TypeError, ValueError):
                return None

        trailing_pe = val(detail, "trailingPE")
        forward_pe = val(detail, "forwardPE")
        roe = val(financial, "returnOnEquity")
        roa = val(financial, "returnOnAssets")
        margin = val(financial, "profitMargins")
        operating_margin = val(financial, "operatingMargins")
        revenue_growth = val(financial, "revenueGrowth")
        earnings_growth = val(financial, "earningsGrowth")
        debt_to_equity = val(financial, "debtToEquity")
        current_ratio = val(financial, "currentRatio")
        price_to_book = val(stats, "priceToBook")
        peg = val(stats, "pegRatio")
        ev_to_ebitda = val(detail, "enterpriseToEbitda")
        total_revenue = val(financial, "totalRevenue")
        total_assets = val(financial, "totalAssets")
        current_liabilities = val(financial, "totalCurrentLiabilities")
        roce = None
        roce_basis = "not available"
        if (
            operating_margin is not None
            and total_revenue
            and total_assets is not None
            and current_liabilities is not None
        ):
            capital_employed = total_assets - current_liabilities
            if capital_employed > 0:
                roce = (operating_margin * total_revenue) / capital_employed
                roce_basis = "estimated from operating margin and capital employed"

        ratios = {
            "pe_ratio": trailing_pe,
            "forward_pe": forward_pe,
            "pb_ratio": price_to_book,
            "peg_ratio": peg,
            "roce": roce,
            "roce_basis": roce_basis,
            "roe": roe,
            "roa": roa,
            "profit_margin": margin,
            "operating_margin": operating_margin,
            "revenue_growth": revenue_growth,
            "earnings_growth": earnings_growth,
            "debt_to_equity": debt_to_equity,
            "current_ratio": current_ratio,
            "ev_to_ebitda": ev_to_ebitda,
            "sector": profile.get("industry") or profile.get("sector"),
        }
        score, drivers = _score(ratios)
        return {
            "available": True,
            "score": round(score, 2),
            "ratios": ratios,
            "influential_metrics": drivers,
            "warnings": [],
            "source": "Yahoo Finance public quoteSummary endpoint",
        }
    except Exception as exc:
        return _empty(f"Fundamental data unavailable: {exc}")


def _empty(warning: str) -> dict[str, Any]:
    return {
        "available": False,
        "score": 0.0,
        "ratios": {},
        "influential_metrics": [],
        "warnings": [warning],
        "source": "",
    }


def _score(r: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    score = 0.0
    drivers: list[dict[str, Any]] = []

    def add(
        metric: str,
        value: float | None,
        points: float,
        reason: str,
        percent: bool = False,
    ) -> None:
        nonlocal score
        if value is None:
            return
        score += points
        if abs(points) >= 5:
            drivers.append(
                {
                    "metric": metric,
                    "value": round(value * 100, 2) if percent else round(value, 2),
                    "impact": round(points, 2),
                    "reason": reason,
                }
            )

    roe = r.get("roe")
    if isinstance(roe, (int, float)):
        add(
            "ROE",
            roe,
            20 if roe >= 0.20 else 10 if roe >= 0.15 else -15 if roe < 0.08 else 0,
            "Strong shareholder return" if roe >= 0.15 else "Weak shareholder return",
            True,
        )
    roce = r.get("roce")
    if isinstance(roce, (int, float)):
        add(
            "ROCE",
            roce,
            20 if roce >= 0.20 else 10 if roce >= 0.12 else -15 if roce < 0.08 else 0,
            "Strong capital efficiency" if roce >= 0.12 else "Weak capital efficiency",
            True,
        )
    pe = r.get("pe_ratio")
    if isinstance(pe, (int, float)) and pe > 0:
        add(
            "P/E",
            pe,
            10 if pe < 15 else 5 if pe < 25 else -10 if pe > 40 else 0,
            "Low earnings valuation" if pe < 25 else "High earnings valuation",
        )
    fpe = r.get("forward_pe")
    if isinstance(pe, (int, float)) and isinstance(fpe, (int, float)) and pe > 0 and fpe > 0:
        delta = (fpe / pe) - 1
        add(
            "Forward P/E change",
            delta * 100,
            8 if delta <= -0.10 else -8 if delta >= 0.10 else 0,
            "Forward valuation improves" if delta <= -0.10 else "Forward valuation worsens",
        )
    debt = r.get("debt_to_equity")
    if isinstance(debt, (int, float)):
        add(
            "Debt/Equity",
            debt,
            8 if debt < 50 else -15 if debt > 150 else 0,
            "Low balance-sheet leverage" if debt < 50 else "High balance-sheet leverage",
        )
    growth = r.get("revenue_growth")
    if isinstance(growth, (int, float)):
        add(
            "Revenue growth",
            growth,
            10 if growth >= 0.15 else 5 if growth >= 0.05 else -10 if growth < 0 else 0,
            "Strong revenue growth" if growth >= 0.05 else "Revenue contraction",
            True,
        )
    earnings = r.get("earnings_growth")
    if isinstance(earnings, (int, float)):
        add(
            "Earnings growth",
            earnings,
            10 if earnings >= 0.15 else 5 if earnings >= 0.05 else -10 if earnings < 0 else 0,
            "Strong earnings growth" if earnings >= 0.05 else "Earnings contraction",
            True,
        )
    margin = r.get("profit_margin")
    if isinstance(margin, (int, float)):
        add(
            "Profit margin",
            margin,
            8 if margin >= 0.15 else -8 if margin < 0.05 else 0,
            "Healthy profitability" if margin >= 0.15 else "Thin profitability",
            True,
        )
    peg = r.get("peg_ratio")
    if isinstance(peg, (int, float)) and peg > 0:
        add(
            "PEG",
            peg,
            8 if peg < 1 else -8 if peg > 2 else 0,
            "Growth-adjusted valuation is attractive" if peg < 1 else "Growth-adjusted valuation is stretched",
        )
    return max(-100.0, min(100.0, score)), sorted(
        drivers, key=lambda x: abs(x["impact"]), reverse=True
    )
