# Automatic market discovery

TradingAlgo now supports an open-ended advisory request where the user does not provide tickers.

The workflow is deliberately two-stage:

1. A configured market-universe provider returns a point-in-time candidate universe.
2. `MarketDiscovery` ranks the universe using transparent screening factors.
3. Only the top shortlist is passed to `IntelligenceOrchestrator.collect()`.
4. Each shortlisted stock receives the normal evidence, technical, fundamental, event and valuation analysis.
5. Final recommendations are ranked using the full advisory score multiplied by advisory confidence. The discovery score is only a tie-breaker.

This prevents the presentation or LLM layer from selecting stocks without first running the market screen and then the full analysis.

## Provider contract

The universe provider returns a normal `ProviderResponse`. The payload can be a list or a dictionary containing one of `candidates`, `stocks`, `symbols`, `results`, or `data`.

Each row should contain at least `ticker` or `symbol`. Optional pre-screen fields include:

- `score`
- `momentum`
- `trend`
- `fundamentals`
- `catalyst`
- `liquidity`
- `risk`
- `market`
- `name`
- `rationale`

If `score` is absent, the scanner calculates a transparent score from those factors. The source provider remains the authority for the candidate universe; the system does not invent tickers when the provider fails.

## Application pattern

```python
from tradingalgo.intelligence import FetchCandidate, IntelligenceOrchestrator
from tradingalgo.intelligence.models import Horizon

result = orchestrator.recommend_market(
    FetchCandidate("market_screen", fetch_market_universe),
    analysis_fetchers=build_fetchers_for_ticker,
    market="US",
    shortlist=10,
    recommendations=5,
    horizon=Horizon.SWING,
)

for recommendation in result.recommendations:
    print(recommendation.analysis.advisory)
```

`build_fetchers_for_ticker(ticker)` should return the configured fetchers for quote, analyst, news, SEC, macro and events for that ticker. Those fetchers reuse the existing provider-health, provenance, freshness and point-in-time controls.

## Safety and quality rules

- No universe provider data means no automatic recommendations.
- Candidate ranking and final advisory ranking remain separate.
- Full analysis is required before a stock enters the final recommendation list.
- Provider failures are returned in `errors` rather than replaced with guessed data.
- `as_of` can be supplied for reproducible historical scans and backtests.
- The feature remains advisory-only and does not submit brokerage orders.
