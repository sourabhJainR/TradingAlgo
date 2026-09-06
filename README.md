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

## Current status

Batch 1 is complete: advisory domain contracts, technical indicators, signal fusion, market-regime foundation, source-policy documentation and incremental progress tracking are in place.

Next: source adapters, SEC ingestion, research storage, event-impact mapping, analyst/sentiment aggregation, geopolitical exposure mapping, outcome tracking, validation and reporting/API.

See `src/tradingalgo/intelligence/README.md` and `docs/progress.html`.
