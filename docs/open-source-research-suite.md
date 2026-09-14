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

Example:

```text
/api/screen?tickers=NVDA,MSFT,AVGO,AMD&market=US&horizon=short&min_score=60&max_rsi=70&breakout_only=true
```

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

Summarizes the analyzed discovery sample into:

- BUY/WATCH/AVOID counts
- BUY percentage
- average score
- average confidence
- breakout count

The response explicitly identifies that this is a discovery sample rather than a claim about the entire exchange.

## Open-source patterns incorporated

The design was informed by recurring capabilities in open-source projects such as:

- full-market technical scanning and custom rule screening
- paper-portfolio diagnostics
- strategy backtesting and risk metrics
- market breadth and regime views
- sector/relative-strength research
- transparent multi-factor ranking
- deterministic alerts
- natural-language research interfaces as a future extension

Examples reviewed included Stock Analyzer, Open-Papertrade, NSE Stock Scanner, AlphaForge, Quantitative Investing Assistant and other open-source research platforms.

The implementation is independently structured for TradingAlgo and does not copy their code.

## Dependency boundary

No paid service is required for these features.

- US historical backtests: public Stooq CSV
- India historical backtests: public NSE historical endpoint
- Individual analysis: existing provider hierarchy
- Portfolio/screener/alerts: local deterministic computation
- No broker connection
- No order execution

Optional provider credentials remain optional where supported by the existing application.

## Safety boundary

Backtests are historical simulations. They do not guarantee future performance. Results should be interpreted together with data quality, transaction costs, taxes, liquidity and market-regime changes.

TradingAlgo remains research/advisory-only.
