# Live data channels

TradingAlgo uses provider adapters so the intelligence engine is independent of any single vendor.

## Current channels

| Channel | Provider | Primary use | Key |
|---|---|---|---|
| Market quote / OHLCV / technicals / news | Alpha Vantage | price, indicators, news sentiment | `ALPHAVANTAGE_API_KEY` |
| Analyst / estimates / company news | Finnhub | recommendation trends, targets, upgrades, estimates and news | `FINNHUB_API_KEY` |
| Filings / XBRL | SEC EDGAR | 10-K, 10-Q, 8-K, 20-F, company facts | none; descriptive `SEC_USER_AGENT` required |
| Macro | FRED | rates, inflation, employment, liquidity and other economic series | `FRED_API_KEY` |
| Global event/news discovery | GDELT | geopolitical and cross-border event/news context | no key in the current adapter |

Alpha Vantage documents daily/intraday market data, technical indicators and market news/sentiment. Finnhub exposes analyst recommendation trends, price targets, upgrades/downgrades, estimates, earnings and SEC filing endpoints. SEC EDGAR APIs provide submissions and XBRL company facts without API keys, with real-time dissemination subject to SEC access policies. FRED provides REST APIs for economic observations and revisions. GDELT is used as a discovery layer for global news/event context.

## Freshness rules

Every fetched response records provider, endpoint and UTC fetch time. The evidence layer additionally records publication time where available and converts age into a freshness factor. A stale event cannot retain full confidence indefinitely.

## Provider policy

- No secrets are stored in source control.
- Providers are optional; missing credentials degrade coverage rather than fabricate data.
- Rate limits and vendor terms must be respected.
- TradingView/Screener data should be connected through permitted/licensed access or user exports; this project will not bypass access controls.
- Provider facts remain distinct from derived signals so recommendations remain auditable.
