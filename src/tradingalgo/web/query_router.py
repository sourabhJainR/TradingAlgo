from __future__ import annotations

import re
from typing import Any


def route_query(text: str) -> dict[str, Any]:
    """Translate common research questions into deterministic application intents.

    This is intentionally local and rule-based. It does not require an LLM, API key,
    remote prompt service, or execution capability.
    """
    query = " ".join(text.strip().split())
    if not query:
        raise ValueError("query is required")
    lower = query.lower()
    market = "India" if any(word in lower for word in ("india", "indian", "nse", "bse")) else "US"
    horizon = "long" if any(word in lower for word in ("long term", "long-term", "invest", "years")) else "short"

    tickers = _tickers(query)
    if any(word in lower for word in ("backtest", "back test", "historical test")) and tickers:
        strategy = "breakout" if "breakout" in lower else "mean_reversion" if "mean reversion" in lower else "sma_cross"
        return {"intent": "backtest", "ticker": tickers[0], "market": market, "strategy": strategy, "horizon": horizon}
    if any(word in lower for word in ("portfolio", "holdings", "allocation")) and ":" in query:
        return {"intent": "portfolio", "holdings": _holdings(query), "market": market, "horizon": horizon}
    if any(word in lower for word in ("compare", "versus", " vs ", "against")) and len(tickers) >= 2:
        return {"intent": "compare", "tickers": tickers[:10], "market": market, "horizon": horizon}
    if any(word in lower for word in ("alert", "signal", "setup", "oversold", "overbought")) and tickers:
        return {"intent": "alerts", "ticker": tickers[0], "market": market, "horizon": horizon}
    if any(word in lower for word in ("screen", "screener", "filter", "breakout stocks")) and tickers:
        return {"intent": "screen", "tickers": tickers[:25], "market": market, "horizon": horizon}
    if tickers:
        return {"intent": "analyze", "ticker": tickers[0], "market": market, "horizon": horizon}
    if any(word in lower for word in ("pulse", "breadth", "market mood", "market health", "market regime")):
        return {"intent": "pulse", "market": market, "horizon": horizon}
    if any(word in lower for word in ("ideas", "opportunities", "recommend", "stocks to buy", "top stocks", "best stocks")):
        return {"intent": "recommend", "market": market, "horizon": horizon}
    raise ValueError("Could not map the question. Try 'analyze NVDA', 'compare NVDA MSFT', 'backtest NVDA breakout', 'top short-term US ideas', or 'market pulse India'.")


def _tickers(text: str) -> list[str]:
    candidates = re.findall(r"\b[A-Z]{2,6}(?:\.[A-Z]{1,3})?\b", text)
    ignored = {"US", "USA", "INDIA", "INDIAN", "NSE", "BSE", "BUY", "SELL", "RSI", "MACD", "SMA", "ETF", "AND", "THE", "FOR", "WITH", "FROM", "TOP"}
    return [item for item in candidates if item not in ignored]


def _holdings(text: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for ticker, weight in re.findall(r"\b([A-Za-z]{2,6})\s*:\s*(\d+(?:\.\d+)?)", text):
        result[ticker.upper()] = float(weight)
    return result
