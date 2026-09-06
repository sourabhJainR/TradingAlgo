from datetime import datetime, timezone

from tradingalgo.data.providers import ProviderResponse
from tradingalgo.intelligence.exposure import ExposureMap
from tradingalgo.intelligence.models import Evidence, Polarity, SourceType
from tradingalgo.intelligence.orchestrator import FetchCandidate, IntelligenceOrchestrator
from tradingalgo.intelligence.persistent_store import SQLiteEvidenceStore


def response(provider, payload):
    return ProviderResponse(provider, "test://endpoint", datetime.now(timezone.utc), payload)


def test_orchestrator_wires_sec_and_fred(tmp_path):
    sec_payload = {"facts": {"us-gaap": {"Revenue": {"units": {"USD": [{"val": 100, "end": "2026-06-30", "filed": "2026-08-01", "form": "10-Q", "accn": "x"}]}}}}}
    fred_payload = {"series_id": "CPIAUCSL", "observations": [{"date": "2026-06-01", "value": "320"}, {"date": "2026-07-01", "value": "322"}]}
    store = SQLiteEvidenceStore(tmp_path / "evidence.sqlite3")
    result = IntelligenceOrchestrator(store=store).collect(
        "TEST",
        sec=[FetchCandidate("sec_edgar", lambda: response("sec_edgar", sec_payload))],
        fred=[FetchCandidate("fred", lambda: response("fred", fred_payload))],
    )
    assert any(item.source_type is SourceType.SEC_FILING for item in result.evidence)
    assert any(item.source_type is SourceType.MACRO for item in result.evidence)
    assert len(store.list_ticker("TEST")) == len(result.evidence)


def test_exposure_mapping_enriches_entity_sector():
    evidence = Evidence(
        id="e1", ticker="NVDA", source_type=SourceType.NEWS, source_name="test",
        observed_at=datetime.now(timezone.utc), title="x", summary="y", polarity=Polarity.BULLISH,
    )
    mapping = ExposureMap(
        ticker_to_entity={"NVDA": "NVIDIA"},
        ticker_to_sector={"NVDA": "Semiconductors"},
        entity_to_tickers={"NVIDIA": ("NVDA", "NVDAW")},
    )
    enriched = mapping.enrich(evidence)
    assert enriched.entity == "NVIDIA"
    assert enriched.sector == "Semiconductors"
    assert enriched.affected_tickers == ["NVDA", "NVDAW"]


def test_incremental_store_upserts_same_evidence(tmp_path):
    item = Evidence(
        id="e1", ticker="TEST", source_type=SourceType.NEWS, source_name="test",
        observed_at=datetime.now(timezone.utc), title="same", summary="same",
    )
    store = SQLiteEvidenceStore(tmp_path / "evidence.sqlite3")
    store.upsert_many([item])
    store.upsert_many([item])
    assert len(store.list_ticker("TEST")) == 1
