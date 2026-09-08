"""Evidence-driven IPO screening from public-record facts and market evidence."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .models import Evidence, Polarity, SourceType


@dataclass(frozen=True)
class IPOProfile:
    ticker: str
    company_name: str
    listing_date: str | None = None
    offer_price: float | None = None
    shares_offered: float | None = None
    post_money_shares: float | None = None
    revenue_growth: float | None = None
    gross_margin: float | None = None
    operating_margin: float | None = None
    free_cash_flow_margin: float | None = None
    cash: float | None = None
    debt: float | None = None
    valuation: float | None = None
    dilution_pct: float | None = None
    customer_concentration_pct: float | None = None
    related_party_risk: float = 0.0
    litigation_risk: float = 0.0
    regulatory_risk: float = 0.0
    governance_risk: float = 0.0
    use_of_proceeds_quality: float = 0.5
    source_quality: float = 0.0
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class IPOScore:
    ticker: str
    score: float
    confidence: float
    verdict: str
    strengths: tuple[str, ...]
    risks: tuple[str, ...]
    missing_data: tuple[str, ...]
    evidence_ids: tuple[str, ...]


def build_ipo_profile(ticker: str, company_name: str, records: Mapping[str, Any], evidence: Sequence[Evidence] = ()) -> IPOProfile:
    """Normalize prospectus/filing/public-record facts without inventing missing values."""
    def num(key: str) -> float | None:
        value = records.get(key)
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None
    ids = tuple(dict.fromkeys(e.id for e in evidence))
    return IPOProfile(
        ticker=ticker.upper(), company_name=company_name,
        listing_date=str(records["listing_date"]) if records.get("listing_date") else None,
        offer_price=num("offer_price"), shares_offered=num("shares_offered"), post_money_shares=num("post_money_shares"),
        revenue_growth=num("revenue_growth"), gross_margin=num("gross_margin"), operating_margin=num("operating_margin"),
        free_cash_flow_margin=num("free_cash_flow_margin"), cash=num("cash"), debt=num("debt"), valuation=num("valuation"),
        dilution_pct=num("dilution_pct"), customer_concentration_pct=num("customer_concentration_pct"),
        related_party_risk=num("related_party_risk") or 0.0, litigation_risk=num("litigation_risk") or 0.0,
        regulatory_risk=num("regulatory_risk") or 0.0, governance_risk=num("governance_risk") or 0.0,
        use_of_proceeds_quality=num("use_of_proceeds_quality") if num("use_of_proceeds_quality") is not None else 0.5,
        source_quality=_source_quality(evidence), evidence_ids=ids,
    )


def analyze_ipo(profile: IPOProfile, evidence: Sequence[Evidence] = ()) -> IPOScore:
    strengths: list[str] = []
    risks: list[str] = []
    missing: list[str] = []
    components: list[float] = []

    def add(name: str, value: float | None, weight: float) -> None:
        if value is None:
            missing.append(name)
        else:
            components.append(value * weight)

    growth = _bounded((profile.revenue_growth or 0.0) / 0.50, -1.0, 1.0) if profile.revenue_growth is not None else None
    margin = _bounded((profile.operating_margin or 0.0) / 0.25, -1.0, 1.0) if profile.operating_margin is not None else None
    fcf = _bounded((profile.free_cash_flow_margin or 0.0) / 0.20, -1.0, 1.0) if profile.free_cash_flow_margin is not None else None
    balance = None if profile.cash is None or profile.debt is None else _bounded((profile.cash - profile.debt) / max(profile.cash + profile.debt, 1.0), -1.0, 1.0)
    dilution = None if profile.dilution_pct is None else _bounded(1.0 - profile.dilution_pct / 100.0, -1.0, 1.0)
    concentration = None if profile.customer_concentration_pct is None else _bounded(1.0 - profile.customer_concentration_pct / 100.0, -1.0, 1.0)

    add("revenue_growth", growth, .22); add("operating_margin", margin, .12); add("free_cash_flow_margin", fcf, .12)
    add("cash_vs_debt", balance, .14); add("dilution", dilution, .08); add("customer_concentration", concentration, .06)
    add("use_of_proceeds", _bounded(2 * profile.use_of_proceeds_quality - 1, -1, 1), .08)
    risk = _bounded((profile.related_party_risk + profile.litigation_risk + profile.regulatory_risk + profile.governance_risk) / 4, 0, 1)
    add("public_record_risk", 1 - 2 * risk, .18)

    score = 50.0 if not components else 50.0 + 50.0 * sum(components) / sum((.22,.12,.12,.14,.08,.06,.08,.18)[i] for i in range(len(components)))
    score = max(0.0, min(100.0, score))
    if growth is not None and growth > .4: strengths.append("strong reported revenue growth")
    if margin is not None and margin > .2: strengths.append("positive operating economics")
    if fcf is not None and fcf > .1: strengths.append("positive free cash flow profile")
    if balance is not None and balance > .2: strengths.append("cash exceeds debt")
    if risk > .4: risks.append("elevated legal, regulatory, related-party or governance risk")
    if concentration is not None and concentration < .5: risks.append("high customer concentration")
    if dilution is not None and dilution < .6: risks.append("material dilution")
    if not missing: missing = []
    coverage = len(components) / 8.0
    confidence = min(1.0, .25 + .65 * coverage + .10 * profile.source_quality)
    verdict = "STRONG" if score >= 70 else "SELECTIVE" if score >= 55 else "AVOID" if score < 40 else "WATCH"
    return IPOScore(profile.ticker, score, confidence, verdict, tuple(strengths), tuple(risks), tuple(missing), profile.evidence_ids)


def public_record_evidence(ticker: str, records: Mapping[str, Any]) -> list[Evidence]:
    """Turn normalized public-record flags into auditable evidence objects."""
    out: list[Evidence] = []
    for key, polarity, severity, summary in (
        ("litigation_risk", Polarity.BEARISH, .8, "Public-record litigation risk flag"),
        ("regulatory_risk", Polarity.BEARISH, .7, "Public-record regulatory risk flag"),
        ("governance_risk", Polarity.BEARISH, .7, "Public-record governance risk flag"),
    ):
        value = records.get(key)
        if value is not None and float(value) > 0:
            out.append(Evidence(id=f"ipo-{ticker.lower()}-{key}", ticker=ticker.upper(), source_type=SourceType.COMPANY_FILING,
                source_name="public_record", observed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                title=summary, summary=f"{summary}: {float(value):.2f}", polarity=polarity, severity=severity,
                confidence=.7, novelty=.8, tags=["ipo", "public_record", key]))
    return out


def _source_quality(evidence: Sequence[Evidence]) -> float:
    if not evidence: return 0.0
    official = sum(e.source_type in {SourceType.SEC_FILING, SourceType.COMPANY_FILING} for e in evidence)
    return min(1.0, .5 * official / len(evidence) + .5)


def _bounded(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
