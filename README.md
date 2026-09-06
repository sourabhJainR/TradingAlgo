# TradingAlgo

TradingAlgo is evolving into a **multi-source investment intelligence and advisory system**. It analyzes market structure, fundamentals, filings, technical charts, analyst revisions, sentiment, sector dynamics, company events, orders/contracts, litigation, M&A, macro and geopolitical developments before producing an evidence-backed advisory view.

It is **analysis-first, not order-execution-first**. The existing event-driven execution/risk boundaries remain isolated so research can mature without silently turning recommendations into trades.

## What the engine considers

- Technical chart: trend, SMA/EMA, RSI, MACD, Bollinger, ATR, volume, support/resistance, relative strength and breakout structure.
- Fundamentals: revenue/earnings growth, margins, FCF, balance sheet, dilution, valuation and earnings quality.
- Analyst recommendations: rating changes, target revisions, estimate revisions and dispersion.
- Market sentiment: news/social sentiment, breadth, volatility and positioning proxies.
- Sector/industry: sector relative strength, earnings revisions, cycle and peer valuation.
- Company events: earnings, guidance, orders, contracts, bookings, launches, management and capital allocation.
- SEC/company filings: periodic filings, 8-K/material events, XBRL facts and insider filings where applicable.
- Legal/regulatory: litigation, investigations, approvals, sanctions and enforcement.
- M&A: acquisitions, divestitures, takeover signals, financing and integration risk.
- Macro/geopolitical: rates, inflation, FX, commodities, tariffs, sanctions, conflicts, elections and supply-chain shocks mapped to affected sectors and companies.

## Core principle

> No recommendation without evidence. No evidence without provenance. No high-conviction view without explicit downside and data-quality checks.

The scoring layer is deliberately transparent. It exposes component signals, confidence, freshness, bull case, bear case and contradictions rather than hiding the decision inside an LLM prompt.

## Architecture

```text
Sources / Licensed APIs / Public Filings / User Exports
        |
        v
Source Adapters -> Canonical Evidence -> Research Store
                                      |
                                      v
       +------------------------------+------------------------------+
       |                              |                              |
   Fundamentals                 Technicals                    Events/NLP
       |                              |                              |
       +---------------+--------------+---------------+--------------+
                       v                              |
                 Market + Sector Regime              |
                       |                              |
                       +---------- Signal Fusion ----+
                                      |
                                      v
                         Bull / Bear / Contradiction
                                      |
                                      v
                              Advisory + Report
                                      |
                                      v
                       Outcome Tracking / Validation
```

## Architecture patterns adopted

The project selectively adapts useful constructs from current open-source implementations: LEAN/NautilusTrader event boundaries; StockOracle-style multi-signal collectors and market-regime gating; EventEdge-style event-driven filings/insider/regulatory research; Siglens and AI Stock Insights style technical/news/fundamental fusion and human-readable reports; and DuckDB/Polars-style analytical storage and vectorized feature processing.

These are design inspirations, not copied implementations or claims of predictive performance.

## Data-source policy

Source adapters must use official APIs, licensed providers, public filings, permitted RSS feeds, or user-provided exports. The system must not bypass access controls or terms of service. For example, Screener documents CSV export rather than an official API, while TradingView restricts non-display processing of its market data. Provider-specific adapters will therefore be pluggable and provenance-aware.

## Deploying the artifact

The supported runtime is **Python 3.11+**. The repository is packaged as a normal Python application and exposes the `tradingalgo` command.

### Option 1: install from a released artifact

If a wheel or source distribution has been produced for a release, copy the artifact to the target machine and install it in an isolated environment:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ./tradingalgo-<version>-py3-none-any.whl
```

For the optional DuckDB/Polars research components:

```bash
python -m pip install './tradingalgo-<version>-py3-none-any.whl[research]'
```

If the delivered artifact is a source archive instead of a wheel, install the archive with the same `pip install ./<artifact>` pattern.

### Option 2: deploy directly from the repository

```bash
git clone https://github.com/sourabhJainR/TradingAlgo.git
cd TradingAlgo
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

For development and tests:

```bash
python -m pip install -e '.[dev,research]'
pytest
```

### Runtime configuration

Configure provider credentials as environment variables on the machine running the advisory service. Do **not** commit API keys to the repository or bake them into the artifact.

```bash
export ALPHAVANTAGE_API_KEY='...'
export FINNHUB_API_KEY='...'
export FRED_API_KEY='...'
export SEC_USER_AGENT='TradingAlgo/0.2.1 contact@example.com'
```

Only configure the providers actually used by the deployment. Missing credentials should result in unavailable-provider handling rather than fabricated data.

### Verify the installed artifact

```bash
tradingalgo --help
tradingalgo run --help
```

The current `run` command is a bootstrap for the isolated execution boundary. **`--mode live` is intentionally rejected.** TradingAlgo currently produces research/advisory intelligence; it does not silently submit brokerage orders.

## Real-time / point-in-time advisory usage

For a real-time advisory request, the application should create a fresh `IntelligenceOrchestrator` and call `collect()` **at the moment the user requests the analysis**. When `as_of` is omitted, the orchestrator uses the current UTC timestamp. Provider adapters are called during that request, so the result reflects the data returned by the configured providers at that point in time.

A typical application integration looks like this:

```python
from tradingalgo.intelligence.orchestrator import FetchCandidate, IntelligenceOrchestrator
from tradingalgo.intelligence.models import Horizon

# provider_fetch() must call your configured/authorized provider and return
# tradingalgo.data.providers.ProviderResponse.
orchestrator = IntelligenceOrchestrator(
    health=health_registry,
    store=evidence_store,
    learning=learning_store,
)

result = orchestrator.collect(
    'NVDA',
    quote=[FetchCandidate('your_market_provider', provider_fetch)],
    analyst=[FetchCandidate('your_analyst_provider', analyst_fetch)],
    news=[FetchCandidate('your_news_provider', news_fetch)],
    sec=[FetchCandidate('sec', sec_fetch)],
    fred=[FetchCandidate('fred', fred_fetch)],
    events=[FetchCandidate('your_event_provider', event_fetch)],
    horizon=Horizon.SWING,
    # Omit as_of for a live request. Set it explicitly for reproducible
    # historical/research runs.
)

print(result.advisory)
```

### Important point-in-time rule

There are two different operating modes:

1. **Live advisory:** omit `as_of`. The system timestamps the request with the current UTC time and asks configured providers for their current permitted data.
2. **Historical/research replay:** provide an explicit `as_of` timestamp. Evidence and factor calculations must not use information published or observed after that timestamp.

Example:

```python
from datetime import datetime, timezone

result = orchestrator.collect(
    'NVDA',
    quote=quote_candidates,
    news=news_candidates,
    sec=sec_candidates,
    as_of=datetime(2026, 9, 6, 10, 30, tzinfo=timezone.utc),
)
```

This distinction is essential: a live result is allowed to use information available now; a historical result must be reproducible without look-ahead leakage.

## Recommended real-time service pattern

For an application, API, dashboard or terminal, keep the advisory engine behind a thin request layer:

```text
User request
     |
     v
API / CLI / Dashboard
     |
     v
Create request timestamp (UTC)
     |
     v
IntelligenceOrchestrator.collect()
     |
     +--> market provider
     +--> analyst provider
     +--> news/events providers
     +--> SEC/company filings
     +--> macro provider
     |
     v
Normalize + deduplicate + freshness checks
     |
     v
Technical / Fundamental / Event / Valuation factors
     |
     v
Transparent scoring + contradictions + risks
     |
     v
Advisory response with evidence and timestamps
```

For repeated requests, do not treat a cached advisory as live merely because the application is running continuously. Cache raw evidence and historical results for auditability, but enforce provider-specific freshness/TTL rules before presenting an item as current. A fresh request should re-fetch data whose freshness window has expired.

A production deployment should also:

- Use UTC internally and convert to the user's timezone only at the UI boundary.
- Preserve `observed_at` and `published_at` for every evidence item.
- Show the provider and source timestamp alongside important inputs.
- Surface provider failures and stale data instead of filling gaps with guessed values.
- Keep API credentials in a secret manager/environment, never in source control.
- Respect each provider's rate limits, licensing and redistribution terms.
- Persist prediction snapshots so the exact advisory state can later be linked to realized outcomes.
- Keep order execution disabled unless a separately validated broker adapter and explicit safety controls are introduced.

## Real-time input freshness

"Real-time" means **freshness is determined by the configured data source and entitlement**, not by the TradingAlgo process itself. Some market feeds may be delayed or end-of-day, while filings/news/events have their own publication and ingestion latency. The advisory must therefore expose freshness and provenance rather than claiming that every input is tick-real-time.

The system's provider-health layer also records failures and temporarily gates repeatedly failing providers. When a provider is unavailable, the remaining evidence can still be used, but the resulting data-quality/confidence should reflect the missing coverage.

## Outcome tracking and validation

Each advisory can be persisted as a historical prediction snapshot. Later, realized market outcomes can be attached to the **exact prediction ID**, enabling walk-forward validation, baseline comparison and statistical testing without rewriting history.

For historical validation, use an explicit `as_of` timestamp and historical candles. Never feed future observations into the evidence/factor set used to create that snapshot.

## Current status

The learning/validation layer now includes prediction snapshots, realized outcomes, point-in-time normalization, persistent learning storage, walk-forward validation and baseline/statistical evaluation foundations.

The current runtime remains **advisory-only**. Live brokerage execution is intentionally not enabled.

See `src/tradingalgo/intelligence/README.md` and `docs/progress.html` for implementation details and the incremental project status.
