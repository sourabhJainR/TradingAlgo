# TradingAlgo

A production-oriented, event-driven algorithmic trading platform for research, backtesting, paper trading, and controlled live execution.

## Why Python

TradingAlgo uses Python as the strategy/research control plane. The architecture borrows proven patterns from mature open-source trading systems:

- **QuantConnect LEAN**: modular datafeed, transaction, realtime, setup, and result-processing boundaries.
- **NautilusTrader**: deterministic event-driven design and a clean separation between strategy logic and execution infrastructure.
- **Freqtrade**: practical dry-run, backtesting, persistence, risk controls, and strategy lifecycle.

The project is intentionally not a fork of any of them. It keeps the useful architectural ideas while providing a smaller, broker-agnostic system that can evolve around equities, ETFs, options, and crypto.

## Safety first

The default mode is **paper**. Live trading is opt-in and requires explicit configuration. No API key is committed to the repository.

The execution path includes:

- pre-trade risk checks
- max position and notional limits
- daily loss limits
- stale-data checks
- duplicate/idempotency protection
- order/position reconciliation
- kill switch
- audit events
- paper/live separation

Backtests are not treated as proof of live profitability. Slippage, spreads, latency, partial fills, rejected orders, market gaps, and data quality can materially change results.

## Repository layout

```text
TradingAlgo/
├── src/tradingalgo/
│   ├── core/             # domain events, orders, positions, clock
│   ├── data/             # market-data interfaces and implementations
│   ├── execution/        # broker interfaces and paper/live adapters
│   ├── risk/             # deterministic pre-trade and portfolio risk
│   ├── strategy/         # strategy interfaces and examples
│   ├── backtest/         # deterministic simulation
│   ├── portfolio/        # portfolio state and reconciliation
│   └── app.py            # CLI entry point
├── tests/
├── config/
├── docs/
└── .github/workflows/
```

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
python -m tradingalgo.app --mode paper
```

## Operating modes

- `backtest` — historical deterministic simulation
- `paper` — live market data with simulated orders
- `live` — real broker execution; disabled unless explicitly enabled

## Roadmap

1. Core event/order/risk contracts
2. Deterministic backtest engine
3. Paper broker and audit trail
4. Market-data adapters
5. Interactive Brokers execution adapter
6. Portfolio reconciliation and recovery
7. Strategy library and walk-forward evaluation
8. Metrics, observability, dashboards and alerts
9. ML/AI research layer with strict promotion gates

See `docs/architecture.md` and `docs/progress.html` for the current design and implementation status.
