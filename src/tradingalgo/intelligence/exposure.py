"""Explicit, auditable propagation of entity and sector events."""
from __future__ import annotations
from dataclasses import dataclass, field
from .event_exposure import event_to_evidence
from .models import Evidence

@dataclass(frozen=True)
class ExposureMap:
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
        return evidence.model_copy(update={"entity": entity, "sector": sector, "affected_tickers": affected, "tags": tags})

    def enrich_many(self, evidence: list[Evidence]) -> list[Evidence]:
        return [self.enrich(item) for item in evidence]

    def propagate_event(self, source_ticker: str, title: str, text: str, source_name: str, source_url: str | None = None) -> list[Evidence]:
        base = self.enrich(event_to_evidence(source_ticker, title, text, source_name, source_url))
        targets = [t for t in self._related_tickers(base) if t != base.ticker]
        output = [base]
        for target in targets:
            output.append(base.model_copy(update={
                "id": f"{base.id}:exposure:{target}", "ticker": target,
                "summary": f"Propagated exposure from {base.ticker}: {base.summary}",
                "tags": [*base.tags, "propagated_exposure"],
                "facts": {**base.facts, "source_ticker": base.ticker},
                "confidence": base.confidence * 0.70,
            }))
        return output

    def _related_tickers(self, evidence: Evidence) -> tuple[str, ...]:
        entity = evidence.entity
        sector = evidence.sector
        related = set(evidence.affected_tickers)
        if entity:
            related.update(t.upper() for t in self.entity_to_tickers.get(entity, ()))
        if sector:
            related.update(t.upper() for t in self.sector_to_tickers.get(sector, ()))
        return tuple(sorted(related))
