# Market data integrations

TradingAlgo now separates vendor access from market discovery and intelligence. API keys are supplied through environment variables and are never committed.

## Supported backend APIs

### Twelve Data

Set `TWELVE_DATA_API_KEY`.

The adapter supports:

- global stock catalogs filtered by country or exchange
- market movers
- quotes
- daily/intraday time series

This is the preferred open market-data adapter for the automatic US/India discovery path because the catalog can be filtered to the United States or India.

Example:

```python
from tradingalgo.data import TwelveDataProvider
from tradingalgo.intelligence import twelve_data_universe

provider = TwelveDataProvider()
universe = twelve_data_universe(provider, market="india")
```

For the US, use `market="us"`.

### Alpha Vantage

Set `ALPHAVANTAGE_API_KEY`.

The adapter supports daily OHLCV, quotes, company overview, earnings estimates, market status and US top gainers/losers/most-active data.

Alpha Vantage's mover endpoint is treated as US-only by this project. It is not presented as an India scanner. India discovery should use Twelve Data or another licensed India market provider.

## TradingView and Screener

TradingView does not currently expose a public market-data API; its official documentation states that the available REST API is for broker integrations rather than general data access. TradingView widgets can still be embedded in the web UX for charts, watchlists and market context.

Screener.in is useful as a research UI, but TradingAlgo does not scrape its website or depend on undocumented endpoints. A future licensed/export-based Screener adapter can implement the same `ProviderResponse` contract without changing the scanner or intelligence layer.

## Discovery flow

```text
User asks for ideas without tickers
        |
        v
Configured US/India market provider
        |
        +--> universe/catalog or market movers
        |
        v
Transparent pre-screen
        |
        v
Shortlist
        |
        v
Existing evidence-backed intelligence pipeline
        |
        +--> quote + technicals
        +--> fundamentals / valuation
        +--> news / SEC / macro / events
        +--> provider health + provenance
        |
        v
Final score x confidence
        |
        v
Top recommendations
```

The market provider only supplies candidate data. It does not make the final recommendation. The existing intelligence pipeline must analyze shortlisted candidates before they are returned.

## Data-quality rules

- No provider key is stored in source control.
- No ticker is invented when a provider fails.
- US mover discovery is not reused for India.
- Point-in-time `as_of` support is retained for backtests and leakage protection.
- TradingView is treated as a presentation/UX integration unless a licensed data API becomes available.
- Provider failures are recorded and surfaced rather than silently converted into recommendations.
