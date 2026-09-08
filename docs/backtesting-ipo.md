# Historical backtesting and IPO research

## Backtesting

`tradingalgo.intelligence.backtesting.run_backtest()` replays candles in chronological order and passes only the history available through each `as_of` session to the predictor. It supports warm-up periods, rebalance cadence, optional overlap control, benchmark candles and configurable round-trip transaction costs.

The backtest report includes trade count, mean return, benchmark-relative return, hit rate, compounded return, maximum portfolio drawdown, MAE/MFE and a bootstrap/sign-flip statistical summary. Overlapping positions are disabled by default so a horizon outcome cannot be counted repeatedly as independent capital deployment.

Backtesting is deliberately separated from live execution. A predictor is injected, making the same advisory rules testable without granting the backtester brokerage access.

## IPO research

`tradingalgo.intelligence.ipo_analysis` provides a normalized `IPOProfile` and an auditable `IPOScore`. It is designed to consume facts extracted from prospectuses, SEC/company filings, exchange disclosures and other permitted public records.

The score considers:

- revenue growth
- operating margin and free-cash-flow margin
- cash versus debt
- dilution
- customer concentration
- use of proceeds
- litigation, regulatory, related-party and governance risk
- source quality and missing-data coverage

Missing facts reduce confidence rather than being silently estimated. Public-record risk is retained as a negative factor and evidence IDs are carried into the result.

The intended production flow is:

`public records -> normalized facts -> evidence -> IPO profile -> score -> valuation/context overlay -> advisory -> post-listing outcome tracking`

The analyzer does not treat a high IPO score as a buy recommendation. Offer valuation, lock-ups, insider selling, float, use of proceeds, competitive position, dilution and post-listing price behavior should be evaluated alongside the public-record score.

## Important validation rules

- Never use facts published after the prediction `as_of` timestamp.
- Keep raw source URL, publication date, observed date and provider metadata with every material fact.
- Use adjusted prices consistently when the data provider supplies them.
- Separate gross, cost-adjusted and benchmark-relative returns.
- Require adequate out-of-sample observations before trusting factor calibration.
- Correct for multiple testing when evaluating many factors, horizons or IPO cohorts.
- Do not claim live or real-time data unless the configured provider entitlement supports it.
