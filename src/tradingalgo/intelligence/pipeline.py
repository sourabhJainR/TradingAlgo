from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .fundamentals import normalize_companyfacts
from .macro import macro_evidence, normalize_fred
from .models import Evidence, Horizon, Polarity, SourceType
from .normalizers import normalize_analyst_recommendations, normalize_news, normalize_quote


@dataclass(frozen=True)
class IngestResult:
    ticker: str
    evidence: list[Evidence]
    provider_errors: dict[str, str]


def _financial_evidence(ticker: str, payload: dict[str, Any]) -> list[Evidence]:
    facts = normalize_companyfacts(ticker, payload)
    return [Evidence(
        id=f"sec:xbrl:{fact.ticker}:{fact.concept}:{fact.period_end}:{fact.accession or 'unknown'}",
        ticker=fact.ticker,
        source_type=SourceType.SEC_FILING,
        source_name="sec_edgar",
        observed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        published_at=__import__("datetime").datetime.fromisoformat(fact.filing_date).replace(tzinfo=__import__("datetime").timezone.utc) if fact.filing_date else None,
        title=f"SEC XBRL {fact.concept}",
        summary=f"{fact.concept}={fact.value} {fact.unit} for period ending {fact.period_end}",
        polarity=Polarity.NEUTRAL,
        confidence=.95,
        novelty=.7,
        horizon=Horizon.MEDIUM,
        tags=["sec", "xbrl", fact.concept],
        facts={"concept": fact.concept, "value": fact.value, "unit": fact.unit, "period_end": fact.period_end, "form": fact.form, "accession": fact.accession},
    ) for fact in facts]


def _fred_evidence(ticker: str, payload: dict[str, Any]) -> list[Evidence]:
    observations = normalize_fred(str(payload.get("series_id", "unknown")), payload)
    result: list[Evidence] = []
    for index, observation in enumerate(observations):
        baseline = observations[index - 1].value if index else None
        result.append(macro_evidence(ticker, observation, baseline))
    return result


def normalize_provider_payloads(ticker: str, payloads: dict[str, Any]) -> IngestResult:
    out: list[Evidence] = []
    errors: dict[str, str] = {}
    for source, payload in payloads.items():
        try:
            if source in {'alpha_vantage','finnhub'} and isinstance(payload, dict) and ('Global Quote' in payload or 'c' in payload):
                out.append(normalize_quote(ticker, payload, source))
            elif source == 'finnhub_analyst':
                ev = normalize_analyst_recommendations(ticker, payload if isinstance(payload, list) else [])
                if ev: out.append(ev)
            elif source.endswith('_news') and isinstance(payload, list):
                out.extend(normalize_news(ticker, payload, source))
            elif source in {'sec_edgar_companyfacts', 'sec_companyfacts'} and isinstance(payload, dict):
                out.extend(_financial_evidence(ticker, payload))
            elif source == 'fred' and isinstance(payload, dict):
                out.extend(_fred_evidence(ticker, payload))
        except (TypeError, ValueError, KeyError) as exc:
            errors[source] = str(exc)
    return IngestResult(ticker=ticker.upper(), evidence=out, provider_errors=errors)
