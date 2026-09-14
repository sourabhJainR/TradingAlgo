from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Any

from tradingalgo.data.sources import GdeltSource


@dataclass(frozen=True)
class EventSignal:
    title: str
    url: str
    event_type: str
    direction: str
    weight: float
    impact: float
    recency: float
    source: str
    rationale: str


_EVENT_RULES: tuple[tuple[str, tuple[str, ...], float, int], ...] = (
    ("order_contract", ("order win", "contract award", "awarded contract", "purchase order", "new order", "contract", "orders"), 20.0, 1),
    ("earnings", ("earnings", "profit", "revenue", "guidance", "results"), 18.0, 0),
    ("m_and_a", ("acquisition", "acquires", "merger", "takeover", "buyout", "joint venture"), 25.0, 1),
    ("lawsuit", ("lawsuit", "sued", "litigation", "legal action", "complaint", "class action"), 18.0, -1),
    ("judgment", ("judgment", "judgement", "court ruling", "court order", "verdict", "appeal ruling"), 22.0, 0),
    ("regulatory", ("regulator", "regulatory", "sec", "ftc", "antitrust", "investigation", "probe", "ban"), 20.0, -1),
    ("sanctions", ("sanction", "export control", "tariff", "embargo", "restricted entity"), 22.0, -1),
    ("geopolitical", ("war", "conflict", "missile", "attack", "strait", "geopolitical", "military", "shipping"), 15.0, -1),
    ("product", ("launch", "new product", "approval", "deployment", "partnership"), 12.0, 1),
)

_BULLISH = ("wins", "won", "awarded", "approval", "approved", "settlement", "dismissed", "cleared", "raises guidance", "beats", "record", "partnership")
_BEARISH = ("loss", "loses", "misses", "cuts guidance", "warning", "fine", "penalty", "lawsuit", "investigation", "probe", "ban", "sanction", "attack", "tariff", "downgrade")


def analyze_events(ticker: str, market: str, limit: int = 30) -> dict[str, Any]:
    """Fetch free GDELT news and turn event classes into transparent directional evidence."""
    source = GdeltSource()
    query = f'"{ticker.upper()}" (order OR contract OR earnings OR lawsuit OR judgment OR acquisition OR regulation OR sanctions OR geopolitical OR investigation)'
    try:
        payload = source.news(query, max_records=limit).payload
    except Exception as exc:
        return {
            "available": False,
            "score": 0.0,
            "weight": 0.0,
            "signals": [],
            "warnings": [f"GDELT event feed unavailable: {exc}"],
        }

    rows = payload.get("articles", []) if isinstance(payload, dict) else []
    signals: list[EventSignal] = []
    for row in rows[:limit]:
        title = str(row.get("title") or row.get("name") or "").strip()
        if not title:
            continue
        text = title.lower()
        matched = None
        for event_type, keywords, base_weight, default_direction in _EVENT_RULES:
            if any(keyword in text for keyword in keywords):
                matched = (event_type, base_weight, default_direction)
                break
        if matched is None:
            continue
        event_type, base_weight, default_direction = matched
        direction = _direction(text, default_direction)
        recency = _recency_multiplier(row)
        impact = round(base_weight * recency * direction, 2)
        signals.append(EventSignal(
            title=title,
            url=str(row.get("url") or row.get("url_mobile") or ""),
            event_type=event_type,
            direction="bullish" if direction > 0 else "bearish" if direction < 0 else "mixed",
            weight=base_weight,
            impact=impact,
            recency=recency,
            source=str(row.get("domain") or "GDELT"),
            rationale=_rationale(event_type, direction),
        ))

    signals = _dedupe(signals)
    raw = sum(item.impact for item in signals[:12])
    score = max(-100.0, min(100.0, raw))
    absolute = sum(abs(item.impact) for item in signals[:12])
    return {
        "available": True,
        "score": round(score, 2),
        "weight": round(min(35.0, absolute), 2),
        "signals": [asdict(item) for item in signals[:12]],
        "event_counts": _counts(signals),
        "market": market,
        "query": query,
        "warnings": [],
    }


def _direction(text: str, default: int) -> int:
    bullish = any(term in text for term in _BULLISH)
    bearish = any(term in text for term in _BEARISH)
    if bullish and not bearish:
        return 1
    if bearish and not bullish:
        return -1
    return default


def _recency_multiplier(row: dict[str, Any]) -> float:
    raw = str(row.get("seendate") or row.get("date") or "")
    if not raw:
        return 0.65
    try:
        parsed = datetime.strptime(raw[:14], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return 0.65
    age = datetime.now(timezone.utc) - parsed
    if age <= timedelta(days=1):
        return 1.0
    if age <= timedelta(days=3):
        return 0.85
    if age <= timedelta(days=7):
        return 0.65
    return 0.4


def _rationale(event_type: str, direction: int) -> str:
    side = "positive" if direction > 0 else "negative" if direction < 0 else "uncertain"
    return f"{event_type.replace('_', ' ')} classified as {side} evidence; impact is weighted by event importance and recency."


def _dedupe(signals: list[EventSignal]) -> list[EventSignal]:
    seen: set[str] = set()
    result: list[EventSignal] = []
    for item in sorted(signals, key=lambda value: abs(value.impact), reverse=True):
        key = item.title.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _counts(signals: list[EventSignal]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in signals:
        counts[item.event_type] = counts.get(item.event_type, 0) + 1
    return counts
