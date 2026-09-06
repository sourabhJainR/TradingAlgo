from datetime import datetime, timezone

from tradingalgo.intelligence.factor_engine import build_fundamental_factors
from tradingalgo.intelligence.models import Evidence, Horizon, Polarity, SourceType


def fact(concept: str, value: float, period: str, filed: str) -> Evidence:
    return Evidence(
        id=f"{concept}-{period}", ticker="AAA", source_type=SourceType.SEC_FILING,
        source_name="sec", observed_at=datetime.fromisoformat(filed).replace(tzinfo=timezone.utc),
        published_at=datetime.fromisoformat(filed).replace(tzinfo=timezone.utc), title=concept,
        summary="point-in-time fact", polarity=Polarity.NEUTRAL, confidence=.95, novelty=.5,
        horizon=Horizon.MEDIUM, facts={"concept": concept, "value": value, "period_end": period},
    )


def test_fundamental_factor_uses_only_facts_available_as_of():
    evidence = [
        fact("Revenue", 100, "2025-12-31", "2026-02-01"),
        fact("Revenue", 120, "2026-06-30", "2026-08-01"),
        fact("NetIncomeLoss", 10, "2025-12-31", "2026-02-01"),
        fact("Assets", 200, "2025-12-31", "2026-02-01"),
        fact("LongTermDebtNoncurrent", 30, "2025-12-31", "2026-02-01"),
        fact("CashAndCashEquivalentsAtCarryingValue", 50, "2025-12-31", "2026-02-01"),
    ]
    signals = build_fundamental_factors("AAA", evidence,
        as_of=datetime(2026, 04, 01, tzinfo=timezone.utc))
    assert signals
    assert all("2026-06-30" not in item.evidence_ids for item in signals)
    quality = next(item for item in signals if item.name == "fundamental_quality")
    assert quality.features["profit_margin"] > 0


def test_missing_history_does_not_invent_growth():
    signals = build_fundamental_factors("AAA", [fact("Revenue", 100, "2025-12-31", "2026-02-01")])
    growth = next(item for item in signals if item.name == "fundamental_growth")
    assert growth.features["revenue_growth"] == 0.0
