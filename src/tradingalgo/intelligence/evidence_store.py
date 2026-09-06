"""Deterministic evidence identity and incremental deduplication."""
from __future__ import annotations
from hashlib import sha256
from .models import Evidence

def evidence_key(evidence: Evidence) -> str:
    raw = "|".join((evidence.ticker.upper(), evidence.source_type.value, evidence.source_name, evidence.title.strip().lower(), evidence.published_at.isoformat() if evidence.published_at else evidence.observed_at.isoformat()))
    return sha256(raw.encode()).hexdigest()

def deduplicate(evidence: list[Evidence]) -> list[Evidence]:
    unique: dict[str, Evidence] = {}
    for item in evidence:
        key = evidence_key(item)
        current = unique.get(key)
        if current is None or (item.confidence, item.novelty) > (current.confidence, current.novelty):
            unique[key] = item
    return list(unique.values())
