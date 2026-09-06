from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .normalizers import normalize_quote, normalize_analyst_recommendations, normalize_news
from .models import Evidence

@dataclass(frozen=True)
class IngestResult:
    ticker: str
    evidence: list[Evidence]
    provider_errors: dict[str, str]


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
        except (TypeError, ValueError, KeyError) as exc:
            errors[source] = str(exc)
    return IngestResult(ticker=ticker.upper(), evidence=out, provider_errors=errors)
