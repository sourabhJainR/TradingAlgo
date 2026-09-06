from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EventType(StrEnum):
    EARNINGS = "earnings"
    GUIDANCE = "guidance"
    MERGER_ACQUISITION = "m_and_a"
    LITIGATION = "litigation"
    REGULATORY = "regulatory"
    CONTRACT_ORDER = "contract_order"
    FINANCING = "financing"
    CAPITAL_RETURN = "capital_return"
    LEADERSHIP = "leadership"
    PRODUCT = "product"
    SUPPLY_CHAIN = "supply_chain"
    GEOPOLITICAL = "geopolitical"
    MACRO = "macro"
    OTHER = "other"


@dataclass(frozen=True)
class EventClassification:
    event_type: EventType
    confidence: float
    keywords: tuple[str, ...]


_RULES: tuple[tuple[EventType, tuple[str, ...]], ...] = (
    (EventType.EARNINGS, ("earnings", "quarterly results", "profit", "revenue")),
    (EventType.GUIDANCE, ("guidance", "outlook", "forecast")),
    (EventType.MERGER_ACQUISITION, ("acquisition", "acquire", "merger", "takeover")),
    (EventType.LITIGATION, ("lawsuit", "litigation", "court", "settlement")),
    (EventType.REGULATORY, ("regulator", "regulatory", "sec", "antitrust")),
    (EventType.CONTRACT_ORDER, ("contract", "order", "award", "backlog")),
    (EventType.FINANCING, ("debt", "offering", "financing", "refinancing")),
    (EventType.CAPITAL_RETURN, ("dividend", "buyback", "repurchase")),
    (EventType.LEADERSHIP, ("ceo", "cfo", "resigns", "appointed")),
    (EventType.PRODUCT, ("launch", "product", "platform", "chip")),
    (EventType.SUPPLY_CHAIN, ("supplier", "shortage", "inventory", "supply chain")),
    (EventType.GEOPOLITICAL, ("tariff", "sanction", "war", "conflict", "export control")),
    (EventType.MACRO, ("inflation", "interest rate", "fed", "gdp", "recession")),
)


def classify_event(text: str) -> EventClassification:
    lowered = text.lower()
    matches = [(event, words) for event, words in _RULES if any(word in lowered for word in words)]
    if not matches:
        return EventClassification(EventType.OTHER, 0.2, ())
    event, words = max(matches, key=lambda item: sum(word in lowered for word in item[1]))
    hits = tuple(word for word in words if word in lowered)
    confidence = min(0.95, 0.45 + 0.15 * len(hits))
    return EventClassification(event, confidence, hits)
