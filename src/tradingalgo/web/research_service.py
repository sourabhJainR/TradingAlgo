from __future__ import annotations

from dataclasses import asdict
from typing import Any

from tradingalgo.data.candles import alpha_vantage_daily, finnhub_candles, nse_historical
from tradingalgo.data.sources import AlphaVantageSource, FinnhubSource, NsePublicSource, SourceConfig
from tradingalgo.intelligence.technical_analytics import analyze as analyze_technical

from dataclasses import dataclass


@dataclass(frozen=True)
class StockAnalysis:
    ticker: str
    market: str
    horizon: str
    action: str
    score: float
    confidence: float
    last_price: float | None
    buy_range: tuple[float, float] | None
    stop_loss: float | None
    targets: tuple[float, float] | None
    hypothesis: str
    prediction_basis: list[str]
    favorable_market: str
    sector_news: list[str]
    risks: list[str]
    data_sources: list[str]
    warnings: list[str]
    technical_signals: dict[str, float | str | None]


def analyze_stock(ticker: str, market: str, horizon: str, config: SourceConfig | None = None) -> StockAnalysis:
    """Build a transparent advisory view. It never places an order."""
    cfg = config or SourceConfig.from_env()
    symbol = ticker.strip().upper()
    market_key = market.strip().lower()
    horizon_key = horizon.strip().lower()
    if not symbol:
        raise ValueError("ticker is required")
    if market_key not in {"us", "india"}:
        raise ValueError("market must be US or India")
    if horizon_key not in {"short", "long"}:
        raise ValueError("horizon must be short or long")

    warnings: list[str] = []
    sources: list[str] = []
    candles = []
    quote: dict[str, Any] = {}
    news: list[dict[str, Any]] = []
    sector = ""

    if cfg.alpha_vantage_key:
        provider = AlphaVantageSource(cfg)
        provider_symbol = _alpha_symbol(symbol, market_key)
        try:
            quote = provider.quote(provider_symbol).payload
            sources.append("Alpha Vantage quote")
        except Exception as exc:
            warnings.append(f"Alpha Vantage quote unavailable: {exc}")
        try:
            raw = provider.daily(provider_symbol, outputsize="full").payload
            candles = alpha_vantage_daily(symbol, raw)
            if candles:
                sources.append("Alpha Vantage historical candles")
        except Exception as exc:
            warnings.append(f"Historical candles unavailable: {exc}")
        try:
            payload = provider.news_sentiment(provider_symbol, limit=50).payload
            news = payload.get("feed", []) if isinstance(payload, dict) else []
            if news:
                sources.append("Alpha Vantage news")
        except Exception as exc:
            warnings.append(f"News unavailable: {exc}")
    elif market_key == "india":
        provider = NsePublicSource()
        try:
            payload = provider.quote(symbol).payload
            quote = _nse_quote(payload)
            sources.append("NSE public quote")
            sector = _nse_sector(payload)
        except Exception as exc:
            warnings.append(f"NSE public quote unavailable: {exc}")
        try:
            raw = provider.historical(symbol, days=500).payload
            candles = nse_historical(symbol, raw)
            if candles:
                sources.append("NSE public historical candles")
        except Exception as exc:
            warnings.append(f"NSE public historical data unavailable: {exc}")
    elif cfg.finnhub_key:
        provider = FinnhubSource(cfg)
        provider_symbol = _finnhub_symbol(symbol, market_key)
        try:
            quote = provider.quote(provider_symbol).payload
            sources.append("Finnhub quote")
        except Exception as exc:
            warnings.append(f"Finnhub quote unavailable: {exc}")
        try:
            raw = provider.candles(provider_symbol, days=500).payload
            candles = finnhub_candles(symbol, raw)
            if candles:
                sources.append("Finnhub historical candles")
        except Exception as exc:
            warnings.append(f"Finnhub candles unavailable: {exc}")
    else:
        warnings.append("No free market-data provider is configured for this market")

    last_price = _last_price(quote, candles)
    metrics = _technical_metrics(candles)
    technical_signals = analyze_technical(candles)
    score = _score(metrics, horizon_key)
    action = _action(score)
    confidence = _confidence(metrics, news, sources)
    levels = _levels(last_price, metrics, horizon_key)
    market_view = _market_view(metrics)
    sector_news = _news_lines(news, sector)
    risks = _risks(metrics, market_view, news, warnings)
    basis = _basis(metrics, horizon_key, market_view, sector_news, technical_signals)
    hypothesis = _hypothesis(action, metrics, horizon_key)

    return StockAnalysis(
        ticker=symbol,
        market="US" if market_key == "us" else "India",
        horizon="Short term" if horizon_key == "short" else "Long term",
        action=action,
        score=round(score, 1),
        confidence=round(confidence, 2),
        last_price=round(last_price, 2) if last_price is not None else None,
        buy_range=(round(levels[0], 2), round(levels[1], 2)) if levels else None,
        stop_loss=round(levels[2], 2) if levels else None,
        targets=(round(levels[3], 2), round(levels[4], 2)) if levels else None,
        hypothesis=hypothesis,
        prediction_basis=basis,
        favorable_market=market_view,
        sector_news=sector_news,
        risks=risks,
        data_sources=sources,
        warnings=warnings,
        technical_signals=technical_signals,
    )


def _alpha_symbol(ticker: str, market: str) -> str:
    return ticker if market == "us" else (ticker if "." in ticker else f"{ticker}.BSE")


def _finnhub_symbol(ticker: str, market: str) -> str:
    return ticker if market == "us" else (ticker if ":" in ticker else f"NSE:{ticker}")


def _nse_quote(payload: dict[str, Any]) -> dict[str, Any]:
    info = payload.get("priceInfo", {}) if isinstance(payload, dict) else {}
    security = payload.get("securityWiseDP", {}) if isinstance(payload, dict) else {}
    volume = security.get("tradedVolume") if isinstance(security, dict) else None
    return {"price": info.get("lastPrice"), "volume": volume}


def _nse_sector(payload: dict[str, Any]) -> str:
    meta = payload.get("metadata", {}) if isinstance(payload, dict) else {}
    return str(meta.get("industry") or meta.get("industryInfo") or "")


def _last_price(quote: dict[str, Any], candles: list[Any]) -> float | None:
    for key in ("c", "05. price", "price"):
        value = quote.get(key)
        if value not in (None, ""):
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return float(candles[-1].close) if candles else None


def _technical_metrics(candles: list[Any]) -> dict[str, float]:
    closes = [float(c.close) for c in candles]
    highs = [float(c.high) for c in candles]
    lows = [float(c.low) for c in candles]
    if not closes:
        return {}
    price = closes[-1]
    sma20 = sum(closes[-20:]) / min(20, len(closes))
    sma50 = sum(closes[-50:]) / min(50, len(closes))
    sma200 = sum(closes[-200:]) / min(200, len(closes))
    ranges = [h - l for h, l in zip(highs[-14:], lows[-14:], strict=False)]
    atr = sum(ranges) / len(ranges) if ranges else 0.0
    return {
        "price": price,
        "sma20": sma20,
        "sma50": sma50,
        "sma200": sma200,
        "atr": atr,
        "high20": max(highs[-20:]),
        "low20": min(lows[-20:]),
        "high52": max(highs[-252:]),
        "low52": min(lows[-252:]),
    }


def _score(m: dict[str, float], horizon: str) -> float:
    if not m:
        return 0.0
    p = m["price"]
    score = (
        (30 if p > m["sma20"] else -30)
        + (25 if p > m["sma50"] else -25)
        + (25 if p > m["sma200"] else -25)
    )
    score += 20 if (p > m["high20"] * 0.98 if horizon == "short" else p > m["sma50"]) else -20
    return max(-100.0, min(100.0, score))


def _action(score: float) -> str:
    if score >= 60:
        return "BUY"
    if score <= -40:
        return "AVOID"
    return "WATCH"


def _confidence(m: dict[str, float], news: list[dict[str, Any]], sources: list[str]) -> float:
    if not m:
        return 0.15
    coverage = min(1.0, len(sources) / 4.0)
    return min(0.95, 0.35 + 0.25 * coverage + (0.15 if news else 0.0) + (0.25 if m.get("sma200", 0) else 0.0))


def _levels(price: float | None, m: dict[str, float], horizon: str) -> tuple[float, float, float, float, float] | None:
    if price is None or not m:
        return None
    atr = max(m["atr"], price * 0.01)
    if horizon == "short":
        center = max(m["sma20"], m["low20"])
        low = min(price, center + 0.25 * atr)
        high = max(price, center + 0.75 * atr)
        stop = max(0.01, low - 1.5 * atr)
        t1 = high + 2.0 * atr
        t2 = high + 4.0 * atr
    else:
        center = max(m["sma50"], m["sma200"])
        low = min(price, center * 1.02)
        high = max(price, center * 1.08)
        stop = max(0.01, min(low - 2.0 * atr, m["sma200"] * 0.90))
        t1 = high * 1.20
        t2 = high * 1.35
    return low, high, stop, t1, t2


def _market_view(m: dict[str, float]) -> str:
    if not m:
        return "Unknown: benchmark data is not available"
    p = m["price"]
    if p > m["sma20"] > m["sma50"]:
        return "Favorable for risk-on setups based on the stock trend"
    if p < m["sma20"] < m["sma50"]:
        return "Unfavorable: trend is weak and risk is elevated"
    return "Neutral: trend signals are mixed"


def _news_lines(news: list[dict[str, Any]], sector: str) -> list[str]:
    lines = [str(item.get("headline") or item.get("title") or item.get("summary")).strip() for item in news[:6] if item.get("headline") or item.get("title") or item.get("summary")]
    return lines or [f"No recent {sector + ' ' if sector else ''}news was returned by the configured provider."]


def _basis(m: dict[str, float], horizon: str, market_view: str, news: list[str], signals: dict[str, Any]) -> list[str]:
    if not m:
        return ["Insufficient market-price history; no technical prediction is asserted."]
    basis = [
        f"Price versus 20/50/200-session moving averages: {m['price']:.2f} / {m['sma20']:.2f} / {m['sma50']:.2f} / {m['sma200']:.2f}.",
        f"ATR-based risk distance is {m['atr']:.2f}.",
        f"20-session range is {m['low20']:.2f} to {m['high20']:.2f}.",
        f"52-week range is {m['low52']:.2f} to {m['high52']:.2f}.",
        market_view,
        f"Horizon rule: {horizon} setup; levels are derived from trend, range and ATR rather than a discretionary price guess.",
    ]
    rsi = signals.get("rsi14")
    macd_hist = signals.get("macd_histogram")
    if rsi is not None:
        basis.append(f"RSI(14) is {rsi:.2f}; readings below 30 are treated as oversold and above 70 as overbought.")
    if macd_hist is not None:
        basis.append(f"MACD histogram is {macd_hist:.4f}; positive values indicate short-term momentum is above its signal line.")
    return basis


def _hypothesis(action: str, m: dict[str, float], horizon: str) -> str:
    if not m:
        return "The hypothesis cannot be established until sufficient market data is available."
    if action == "BUY":
        return f"The {horizon} hypothesis is that trend continuation is more likely while price holds above the key moving-average and volatility support levels."
    if action == "AVOID":
        return f"The {horizon} hypothesis is that downside or failed rebounds remain more likely while price stays below the key trend averages."
    return f"The {horizon} hypothesis is inconclusive because the trend signals do not align strongly enough for a directional setup."


def _risks(m: dict[str, float], market_view: str, news: list[dict[str, Any]], warnings: list[str]) -> list[str]:
    risks = [
        "Technical levels can fail after earnings, macro shocks or gap moves.",
        "Stop-loss levels are research levels, not guaranteed execution prices.",
    ]
    if m and m["atr"] > m["price"] * 0.04:
        risks.append("Recent volatility is high relative to price; position sizing should be conservative.")
    if "Unfavorable" in market_view:
        risks.append("The current trend context is unfavorable for long exposure.")
    if news:
        risks.append("News sentiment can change quickly and headlines may be incomplete.")
    if warnings:
        risks.append("Some requested data sources were unavailable, reducing confidence.")
    return risks


def _asdict(result: StockAnalysis) -> dict[str, Any]:
    data = asdict(result)
    data["buy_range"] = list(result.buy_range) if result.buy_range else None
    data["targets"] = list(result.targets) if result.targets else None
    data["advisory_only"] = True
    return data
