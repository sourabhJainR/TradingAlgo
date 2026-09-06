from datetime import datetime, timezone

from tradingalgo.intelligence.decision_engine import decide, evidence_signals
from tradingalgo.intelligence.exposure import ExposureMap
from tradingalgo.intelligence.models import Evidence, Polarity, SourceType, Horizon


def evidence(ticker: str, polarity: Polarity, category: SourceType, severity: float = .5) -> Evidence:
    return Evidence(id=f"{ticker}-{category}", ticker=ticker, source_type=category, source_name="test",
        observed_at=datetime.now(timezone.utc), title="test", summary="test", polarity=polarity,
        severity=severity, confidence=.9, novelty=.9)


def test_entity_and_sector_propagation():
    mapping = ExposureMap(ticker_to_entity={"AAA": "Entity"}, ticker_to_sector={"AAA": "Sector"},
        entity_to_tickers={"Entity": ("AAA", "BBB")}, sector_to_tickers={"Sector": ("CCC",)})
    items = mapping.propagate_event("AAA", "New contract award", "large contract order", "test")
    assert {x.ticker for x in items} == {"AAA", "BBB", "CCC"}
    assert any("propagated_exposure" in x.tags for x in items if x.ticker != "AAA")


def test_decision_engine_fuses_factors_and_reduces_contradiction_confidence():
    items = [evidence("AAA", Polarity.BULLISH, SourceType.FUNDAMENTAL),
             evidence("AAA", Polarity.BEARISH, SourceType.LEGAL)]
    signals = evidence_signals("AAA", items)
    advisory = decide("AAA", signals, items, Horizon.MEDIUM)
    assert advisory.ticker == "AAA"
    assert advisory.signals
    assert advisory.contradictions
    assert 0 <= advisory.confidence <= 1
