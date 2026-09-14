# TradingAlgo research UI

The repository now includes a lightweight research-only web interface. It is intentionally separate from the execution gateway and does not submit broker orders.

## Start

```bash
python -m pip install -e .
tradingalgo web --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080` in a browser.

## What the user can ask

- Analyze a specific US stock.
- Analyze a specific Indian stock.
- Choose short-term or long-term horizon.
- Review the current action, score and confidence.
- Review buy range, stop loss and two research targets.
- Read the hypothesis and the prediction basis.
- See market/trend context, recent company or sector news returned by the configured provider, and explicit risks.
- See data-source warnings when provider coverage is incomplete.

## Data providers

The first configured provider is used:

1. Finnhub when `FINNHUB_API_KEY` is configured.
2. Alpha Vantage when `ALPHAVANTAGE_API_KEY` is configured and Finnhub is not configured.

The service never invents a quote when no provider is configured. It returns a lower-confidence research response with a data warning instead.

## Research contract

The buy range, stop and targets are derived from price history, moving averages, recent range and ATR. They are research levels, not guaranteed execution prices. News is presented as evidence/context and is not treated as a standalone price forecast.

The UI is deliberately thin. The analysis remains in `tradingalgo.web.research_service` so the same result can later be exposed through an API, CLI or another frontend without coupling the domain logic to HTML.
