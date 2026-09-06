"""Explicit entity and sector exposure mapping.

Mappings are supplied by configuration/callers; the system never guesses a
sector or invents affected companies from an event.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from .models import Evidence


@dataclass(frozen=True)
class ExposureMap:
    """Declared security/entity/sector relationships used during composition."""
    ticker_to_entity: dict[str, str] = field(default_factory=dict)
    ticker_to_sector: dict[str, str] = field(default_factory=dict)
    entity_to_tickers: dict[str, tuple[str, ...]] = field(default_factory=dict)
    sector_to_tickers: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def enrich(self, evidence: Evidence) -> Evidence:
        ticker = evidence.ticker.upper()
        entity = evidence.entity or self.ticker_to_entity.get(ticker)
        sector = evidence.sector or self.ticker_to_sector.get(ticker)
        affected = list(dict.fromkeys(t.upper() for t in evidence.affected_tickers))
        if not affected and entity:
            affected.extend(t.upper() for t in self.entity_to_tickers.get(entity, ()))
        if not affected and sector:
            affected.extend(t.upper() for t in self.sector_to_tickers.get(sector, ()))
        if ticker not in affected:
            affected.insert(0, ticker)
        tags = list(evidence.tags)
        for value in (entity, sector):
            if value and value not in tags:
                tags.append(value)
        return evidence.model_copy(update={
            "entity": entity,
            "sector": sector,
            "affected_tickers": affected,
            "tags": tags,
        })

    def enrich_many(self, evidence: list[Evidence]) -> list[Evidence]:
        return [self.enrich(item) for item in evidence]
