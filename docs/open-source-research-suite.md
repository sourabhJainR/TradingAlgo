# Free Open-Source Research Suite

TradingAlgo now incorporates useful patterns seen across open-source stock-analysis and quantitative-research projects while keeping its existing architecture and advisory-only boundary.

## Added capabilities

### Screener

`GET /api/screen`

Screen a user-supplied universe using transparent conditions:

- minimum composite score
- minimum confidence
- BUY/WATCH/AVOID action
- RSI range
- maximum drawdown
- 20-day breakout-only mode

### Backtesting

`GET /api/backtest`

Free historical data is used to test deterministic strategies:

- 20/50 SMA trend following
- 20-day breakout
- mean reversion

The report includes total return, CAGR, Sharpe, maximum drawdown, trade count, win rate, profit factor and buy-and-hold comparison.

The simulator deliberately uses the prior completed candle for signals before applying the next candle's return, avoiding the most common look-ahead mistake.

### Portfolio diagnostics

`GET /api/portfolio`

Analyze a portfolio such as:

```text
NVDA:30,MSFT:25,AVGO:20,VOO:25
```

The service reports:

- normalized weights
- weighted advisory score
- weighted confidence
- largest position
- Herfindahl concentration index
- concentration/AVOID flags

It does not rebalance or place orders.

### Zerodha read-only connector

`GET /api/portfolio/broker?broker=zerodha`

The Zerodha connector reads holdings from Kite Connect using server-side environment variables:

```text
ZERODHA_API_KEY=...
ZERODHA_ACCESS_TOKEN=...
```

The connector normalizes quantity, T+1 quantity and MTF quantity, then preserves average price, last price, invested value, current value and P&L before running the normal portfolio diagnostics.

No order, trade, or account mutation endpoint is exposed.

### INDmoney and Excel/CSV import

`POST /api/portfolio/import`

Upload `.xlsx`, `.xls` or `.csv` files. Select `INDmoney` when importing an INDmoney statement; otherwise select generic Excel/CSV. Common column names are normalized automatically, including Symbol/Security, Quantity, Average Price, LTP, Current Value and P&L.

This is intentionally file-based rather than screen-scraping or automating an INDmoney login. It works with exported statements and keeps the analysis local/read-only. The same importer can accept statements from other brokers.

### Deterministic alerts

`GET /api/alerts?ticker=NVDA&market=US&horizon=short`

Flags observable conditions such as:

- RSI oversold/overbought
- positive/negative MACD histogram
- 20-day breakout
- severe historical drawdown

These are explainable signal flags, not price predictions.

### Market pulse

`GET /api/pulse`

Summarizes the analyzed discovery sample into BUY/WATCH/AVOID counts, BUY percentage, average score, average confidence and breakout count.

The response explicitly identifies that this is a discovery sample rather than a claim about the entire exchange.

## Dependency boundary

No paid service is required for Excel/CSV import or local portfolio diagnostics. Zerodha live holdings require a Kite Connect application and access token supplied by the user; the application does not embed credentials or provide execution.

## Safety boundary

Broker connectors are read-only. Backtests are historical simulations and do not guarantee future performance. Results should be interpreted together with data quality, transaction costs, taxes, liquidity and market-regime changes.

TradingAlgo remains research/advisory-only.
