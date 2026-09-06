from datetime import datetime, timezone
from tradingalgo.data.health import ProviderHealthRegistry
from tradingalgo.data.providers import ProviderResponse
from tradingalgo.intelligence.models import Evidence, Polarity, SourceType
from tradingalgo.intelligence.evidence_composer import compose_evidence
from tradingalgo.intelligence.orchestrator import FetchCandidate, IntelligenceOrchestrator

def response(payload):
    return ProviderResponse(provider="test", endpoint="test", fetched_at=datetime.now(timezone.utc), payload=payload, freshness="fresh")

def test_orchestrator_falls_back_and_composes():
    health = ProviderHealthRegistry()
    orch = IntelligenceOrchestrator(health)
    result = orch.collect("ABC", quote=[FetchCandidate("bad", lambda: (_ for _ in ()).throw(RuntimeError("down"))), FetchCandidate("good", lambda: response({"Global Quote": {"05. price": "100", "10. change percent": "2"}}))])
    assert result.selected_providers["quote"] == "good"
    assert result.evidence
    assert result.bundle.signals
    assert not result.provider_errors

def test_health_gate_skips_unavailable_provider():
    health = ProviderHealthRegistry()
    for _ in range(3): health.record_failure("bad")
    result = IntelligenceOrchestrator(health).collect("ABC", quote=[FetchCandidate("bad", lambda: response({}))])
    assert "bad" in result.provider_errors
    assert not result.evidence

def test_composer_detects_contradiction_and_risk():
    now = datetime.now(timezone.utc)
    evidence = [
        Evidence(id="a", ticker="ABC", source_type=SourceType.ANALYST, source_name="x", observed_at=now, title="Positive revisions", summary="up", polarity=Polarity.BULLISH, severity=.8, confidence=.9),
        Evidence(id="b", ticker="ABC", source_type=SourceType.LEGAL, source_name="x", observed_at=now, title="Legal risk", summary="risk", polarity=Polarity.BEARISH, severity=.8, confidence=.9, tags=["litigation"]),
    ]
    bundle = compose_evidence("ABC", evidence, now=now)
    assert bundle.quality > 0
    assert bundle.contradictions
    assert bundle.risks == ("Legal risk",)
