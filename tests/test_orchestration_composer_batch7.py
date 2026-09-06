from datetime import datetime, timezone

from tradingalgo.data.health import ProviderHealthRegistry
from tradingalgo.data.providers import ProviderResponse
from tradingalgo.intelligence.composer import compose_advisory
from tradingalgo.intelligence.models import Evidence, Horizon, Polarity, SourceType
from tradingalgo.intelligence.orchestrator import FetchCandidate, IntelligenceOrchestrator


def response(provider: str, payload: dict) -> ProviderResponse:
    return ProviderResponse(provider, "test", datetime.now(timezone.utc), payload, "fresh")


def evidence(source_type: SourceType, polarity: Polarity, severity: float) -> Evidence:
    return Evidence(id=f"{source_type}:{polarity}", ticker="ABC", source_type=source_type, source_name="test",
                    observed_at=datetime.now(timezone.utc), title="test", summary="test",
                    polarity=polarity, severity=severity, confidence=.9, horizon=Horizon.SWING)


def test_orchestrator_falls_back_after_provider_failure():
    health = ProviderHealthRegistry()
    calls = []

    def bad():
        calls.append("bad")
        raise RuntimeError("down")

    def good():
        calls.append("good")
        return response("good", {"Global Quote": {"05. price": "100", "10. change percent": "2%"}})

    result = IntelligenceOrchestrator(health).collect(
        "abc", quote=[FetchCandidate("bad", bad), FetchCandidate("good", good)]
    )
    assert calls == ["bad", "good"]
    assert result.selected_providers["quote"] == "good"
    assert result.evidence[0].ticker == "ABC"


def test_composer_fuses_sources_and_surfaces_contradiction():
    items = [
        evidence(SourceType.FUNDAMENTAL, Polarity.BULLISH, .7),
        evidence(SourceType.NEWS, Polarity.BULLISH, .5),
        evidence(SourceType.LEGAL, Polarity.BEARISH, -.8),
    ]
    advisory = compose_advisory("abc", items)
    assert advisory.ticker == "ABC"
    assert advisory.signals
    assert advisory.contradictions
    assert advisory.data_quality > 0


def test_composer_empty_evidence_is_watch():
    advisory = compose_advisory("abc", [])
    assert advisory.action == "WATCH"
    assert advisory.confidence == 0
