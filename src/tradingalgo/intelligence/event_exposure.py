"""Map classified events to ticker exposure."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from .event_taxonomy import classify_event
from .models import Evidence, Horizon, Polarity, SourceType

@dataclass(frozen=True)
class ExposureRule:
    polarity: Polarity
    severity: float
    tags: tuple[str, ...]

_RULES = {
    "litigation": ExposureRule(Polarity.BEARISH, .75, ("litigation", "legal")),
    "regulatory": ExposureRule(Polarity.BEARISH, .65, ("regulatory",)),
    "geopolitical": ExposureRule(Polarity.MIXED, .55, ("geopolitical",)),
    "m_and_a": ExposureRule(Polarity.MIXED, .45, ("m_and_a",)),
    "contract_order": ExposureRule(Polarity.BULLISH, .60, ("contract_order", "catalyst")),
    "guidance": ExposureRule(Polarity.BULLISH, .50, ("guidance",)),
}

def event_to_evidence(ticker: str, title: str, text: str, source_name: str, source_url: str | None = None, published_at: datetime | None = None) -> Evidence:
    published_at = published_at or datetime.now(timezone.utc)
    classification = classify_event(f"{title} {text}")
    rule = _RULES.get(classification.event_type.value)
    polarity = rule.polarity if rule else Polarity.NEUTRAL
    severity = rule.severity if rule else .20
    if polarity is Polarity.MIXED:
        severity = 0.0
    event_type = classification.event_type.value
    source_type = SourceType.GEOPOLITICAL if event_type == "geopolitical" else SourceType.LEGAL if event_type in {"litigation", "regulatory"} else SourceType.M_AND_A if event_type == "m_and_a" else SourceType.NEWS
    digest = hashlib.sha256(f"{ticker.upper()}|{title}|{text}".encode()).hexdigest()[:16]
    return Evidence(id=f"{source_name}:event:{digest}", ticker=ticker.upper(), source_type=source_type, source_name=source_name, source_url=source_url, observed_at=published_at, published_at=published_at, title=title, summary=text, polarity=polarity, severity=severity, confidence=classification.confidence, novelty=.8, horizon=Horizon.SWING, tags=list(rule.tags if rule else (event_type,)), facts={"event_type": event_type, "keywords": classification.keywords})
