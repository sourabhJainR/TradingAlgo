# Investment Intelligence Layer

TradingAlgo is evolving from an execution-first trading skeleton into a **research and advisory engine**. Execution remains isolated and disabled by default for this workstream.

## Signal map

Every recommendation should consider, where data is available:

1. **Technical chart** — trend, moving averages, RSI, MACD, Bollinger position, ATR/volatility, volume, relative strength, support/resistance and breakout structure.
2. **Fundamentals** — revenue/earnings growth, margins, cash flow, balance sheet, dilution, valuation and earnings quality.
3. **Analyst view** — rating distribution, target-price changes, estimate revisions and dispersion. Analyst data is treated as evidence, not truth.
4. **Market sentiment** — news/social sentiment, breadth, volatility regime and positioning proxies.
5. **Sector/industry** — sector relative strength, sector earnings revisions, supply/demand cycle and peer valuation.
6. **Company events** — earnings, guidance, orders, contracts, bookings, product launches, management changes and capital allocation.
7. **Legal/regulatory** — litigation, investigations, regulatory approvals/actions and material compliance events.
8. **M&A** — acquisitions, divestitures, takeovers, financing and integration risks.
9. **SEC/company filings** — 10-K/10-Q/8-K, insider forms and XBRL facts for US securities; local exchange/company filings through licensed or public sources for other markets.
10. **Geopolitics/macro** — rates, inflation, FX, commodities, tariffs, sanctions, conflicts, elections and supply-chain shocks, mapped to affected sectors and tickers.

## Evidence contract

A material fact is represented as an `Evidence` record with source, publication/observation time, confidence, novelty, polarity, severity, horizon and optional URL. This prevents an LLM summary from becoming an unsupported recommendation.

## Decision contract

The fusion engine produces:

- score and confidence
- bull case
- bear case
- contradictions
- risks and catalysts
- signal-level evidence IDs
- data-quality score
- explicit horizon

Missing or stale data reduces confidence; it does not silently become neutral evidence.

## Important source constraints

Use official/licensed APIs, public filings, RSS feeds, exports supplied by the user, or other permitted interfaces. Do **not** build a scraper that bypasses access controls or terms of service. Screener provides CSV export rather than an official API, while TradingView's own policy restricts non-display use of its content/market data. The adapter boundary therefore supports user exports and licensed providers instead of assuming unrestricted scraping.

## Research patterns adopted

The architecture selectively adopts proven constructs from current open-source implementations:

- DuckDB + Polars style columnar research pipelines for large joins and feature generation.
- Multi-signal collectors and market-regime gating from StockOracle-like systems.
- Event-driven SEC/insider/regulatory strategies from EventEdge-like systems.
- Technical + news + fundamentals + macro fusion and human-readable reports from Siglens/AI Stock Insights-like systems.
- Deterministic event boundaries and isolated execution concepts inspired by LEAN/NautilusTrader.

These are architectural inspirations, not copied code or claims of predictive performance.
