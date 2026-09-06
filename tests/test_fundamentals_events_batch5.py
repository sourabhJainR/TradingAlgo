from tradingalgo.intelligence.event_taxonomy import EventType, classify_event
from tradingalgo.intelligence.fundamentals import normalize_companyfacts


def test_companyfacts_latest_fact() -> None:
    payload = {"facts": {"us-gaap": {"Revenue": {"units": {"USD": [
        {"val": 100, "end": "2025-12-31", "filed": "2026-02-01", "form": "10-K", "accn": "x"},
    ]}}}}}
    facts = normalize_companyfacts("ABC", payload)
    assert len(facts) == 1
    assert facts[0].concept == "Revenue"
    assert facts[0].value == 100


def test_event_taxonomy_detects_m_and_a() -> None:
    result = classify_event("Company announces acquisition of a strategic supplier")
    assert result.event_type == EventType.MERGER_ACQUISITION
    assert result.confidence > 0.4
