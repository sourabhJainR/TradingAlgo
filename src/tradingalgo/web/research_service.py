from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from tradingalgo.data.candles import alpha_vantage_daily, finnhub_candles, nse_historical
from tradingalgo.data.sources import AlphaVantageSource, FinnhubSource, NsePublicSource, SourceConfig
from tradingalgo.intelligence.event_intelligence import analyze_events
from tradingalgo.intelligence.fundamentals import analyze_fundamentals
from tradingalgo.intelligence.technical_analytics import analyze as analyze_technical


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
    fundamental_signals: dict[str, Any]
    event_signals: dict[str, Any]
    score_weights: dict[str, float]
    score_components: dict[str, float]
    next_move: str
    next_move_probability: float


def _score_weights(horizon: str) -> dict[str, float]:
    if horizon == "long":
        return {
            "technical": 0.35,
            "fundamentals": 0.30,
            "corporate_events": 0.15,
            "legal_regulatory": 0.10,
            "geopolitical": 0.10,
        }
    return {
        "technical": 0.50,
        "fundamentals": 0.15,
        "corporate_events": 0.15,
        "legal_regulatory": 0.10,
        "geopolitical": 0.10,
    }


def analyze_stock(ticker: str, market: str, horizon: str, config: SourceConfig | None = None) -> StockAnalysis:
    """Build a transparent advisory view using technicals, fundamentals and weighted public events."""
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
    technical_score = _technical_score(metrics, technical_signals, horizon_key)

    fundamental_signals = analyze_fundamentals(symbol, "US" if market_key == "us" else "India")
    warnings.extend(fundamental_signals.get("warnings", []))
    if fundamental_signals.get("available"):
        sources.append(str(fundamental_signals.get("source") or "Public fundamental data"))

    event_signals = analyze_events(symbol, "US" if market_key == "us" else "India")
    warnings.extend(event_signals.get("warnings", []))
    if event_signals.get("available"):
        sources.append("GDELT public event/news intelligence")

    components = _event_components(event_signals)
    score_weights = _score_weights(horizon_key)
    score_components = {
        "technical": round(technical_score, 2),
        "fundamentals": round(float(fundamental_signals.get("score", 0.0)), 2),
        "corporate_events": round(components["corporate_events"], 2),
        "legal_regulatory": round(components["legal_regulatory"], 2),
        "geopolitical": round(components["geopolitical"], 2),
    }
    score = sum(score_weights[key] * score_components[key] for key in score_weights)
    action = _action(score)
    confidence = _confidence(metrics, event_signals, fundamental_signals, sources)
    levels = _levels(last_price, metrics, horizon_key)
    market_view = _market_view(metrics)
    sector_news = _news_lines(news, sector)
    risks = _risks(metrics, market_view, news, event_signals, warnings, fundamental_signals)
    basis = _basis(metrics, horizon_key, market_view, technical_signals, fundamental_signals, event_signals, score_components, score_weights)
    hypothesis = _hypothesis(action, metrics, horizon_key, event_signals, fundamental_signals)
    next_move, probability = _next_move(score, technical_signals, event_signals)

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
        fundamental_signals=fundamental_signals,
        event_signals=event_signals,
        score_weights=score_weights,
        score_components=score_components,
        next_move=next_move,
        next_move_probability=round(probability, 2),
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


def _technical_score(m: dict[str, float], signals: dict[str, Any], horizon: str) -> float:
    if not m:
        return 0.0
    p = m["price"]
    score = (30 if p > m["sma20"] else -30) + (25 if p > m["sma50"] else -25) + (25 if p > m["sma200"] else -25)
    score += 20 if (p > m["high20"] * 0.98 if horizon == "short" else p > m["sma50"]) else -20
    if signals.get("macd_histogram") is not None:
        score += 5 if float(signals["macd_histogram"]) > 0 else -5
    if signals.get("rsi14") is not None:
        rsi = float(signals["rsi14"])
        if 45 <= rsi <= 65:
            score += 5
        elif rsi > 75:
            score -= 5
        elif rsi < 25:
            score += 2
    pattern = signals.get("pattern")
    if pattern in {"bullish_breakout", "higher_highs_higher_lows", "double_bottom_candidate"}:
        score += 10
    if pattern in {"bearish_breakdown", "lower_highs_lower_lows", "double_top_candidate"}:
        score -= 10
    return max(-100.0, min(100.0, score))


def _event_components(event_data: dict[str, Any]) -> dict[str, float]:
    components = {"corporate_events": 0.0, "legal_regulatory": 0.0, "geopolitical": 0.0}
    for row in event_data.get("signals", []):
        event_type = row.get("event_type")
        impact = float(row.get("impact", 0.0))
        if event_type in {"order_contract", "earnings", "m_and_a", "product"}:
            components["corporate_events"] += impact
        elif event_type in {"lawsuit", "judgment", "regulatory"}:
            components["legal_regulatory"] += impact
        elif event_type in {"sanctions", "geopolitical"}:
            components["geopolitical"] += impact
    return {key: max(-100.0, min(100.0, value)) for key, value in components.items()}


def _action(score: float) -> str:
    if score >= 60:
        return "BUY"
    if score <= -40:
        return "AVOID"
    return "WATCH"


def _confidence(m: dict[str, float], events: dict[str, Any], fundamentals: dict[str, Any], sources: list[str]) -> float:
    if not m:
        return 0.15
    coverage = min(1.0, len(sources) / 6.0)
    event_bonus = 0.15 if events.get("available") and events.get("signals") else 0.05 if events.get("available") else 0.0
    fundamental_bonus = 0.10 if fundamentals.get("available") and fundamentals.get("influential_metrics") else 0.0
    return min(0.95, 0.25 + 0.25 * coverage + event_bonus + fundamental_bonus + (0.25 if m.get("sma200", 0) else 0.0))


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


def _basis(m: dict[str, float], horizon: str, market_view: str, signals: dict[str, Any], fundamentals: dict[str, Any], events: dict[str, Any], components: dict[str, float], weights: dict[str, float]) -> list[str]:
    if not m:
        return ["Insufficient market-price history; no technical prediction is asserted."]
    basis = [
        f"Technical weight {weights['technical']:.0%}: price versus 20/50/200-session moving averages is {m['price']:.2f} / {m['sma20']:.2f} / {m['sma50']:.2f} / {m['sma200']:.2f}; technical component is {components['technical']:.1f}.",
        f"Fundamental weight {weights['fundamentals']:.0%}: fundamental component is {components['fundamentals']:.1f}; ROCE/ROE/P-E, growth, margins and leverage are used only when public data is available.",
        f"Corporate-event weight {weights['corporate_events']:.0%}: event component is {components['corporate_events']:.1f}, covering orders, earnings, M&A and product events.",
        f"Legal/regulatory weight {weights['legal_regulatory']:.0%}: event component is {components['legal_regulatory']:.1f}, covering lawsuits, judgments and regulatory actions.",
        f"Geopolitical weight {weights['geopolitical']:.0%}: event component is {components['geopolitical']:.1f}, covering sanctions, conflict and supply/shipping risks.",
        f"Chart pattern: {signals.get('pattern')}; breakout={signals.get('breakout_20d')}, breakdown={signals.get('breakdown_20d')}, RSI={signals.get('rsi14')}, MACD histogram={signals.get('macd_histogram')}, volume ratio={signals.get('volume_ratio_20d')}x.",
        f"ATR-based risk distance is {m['atr']:.2f}; 20-session range is {m['low20']:.2f} to {m['high20']:.2f}.",
        market_view,
        f"Horizon rule: {horizon} setup; levels are derived from trend, range and ATR rather than a discretionary price guess.",
    ]
    for row in fundamentals.get("influential_metrics", [])[:6]:
        basis.append(f"Fundamental driver: {row.get('metric')}={row.get('value')} | impact {float(row.get('impact', 0.0)):+.1f} | {row.get('reason')}.")
    for row in events.get("signals", [])[:5]:
        basis.append(f"Event evidence ({row.get('event_type')}): {row.get('title')} | impact {float(row.get('impact', 0.0)):+.1f}.")
    return basis


def _hypothesis(action: str, m: dict[str, float], horizon: str, events: dict[str, Any], fundamentals: dict[str, Any]) -> str:
    if not m:
        return "The hypothesis cannot be established until sufficient market data is available."
    event_score = float(events.get("score", 0.0))
    fundamental_score = float(fundamentals.get("score", 0.0))
    event_bias = "with event evidence supporting the move" if event_score > 15 else "with event evidence opposing the move" if event_score < -15 else "with mixed or limited event evidence"
    fundamental_bias = " and strong fundamental support" if fundamental_score > 20 else " but fundamental quality is a headwind" if fundamental_score < -20 else " with mixed fundamental evidence"
    if action == "BUY":
        return f"The {horizon} hypothesis is that trend continuation is more likely while price holds key technical support, {event_bias}{fundamental_bias}."
    if action == "AVOID":
        return f"The {horizon} hypothesis is that downside or failed rebounds remain more likely while price stays below key trend levels, {event_bias}{fundamental_bias}."
    return f"The {horizon} hypothesis is inconclusive because technical, fundamental and event evidence does not align strongly enough for a directional setup."


def _next_move(score: float, signals: dict[str, Any], events: dict[str, Any]) -> tuple[str, float]:
    if score >= 20:
        direction = "Higher / bullish bias"
    elif score <= -20:
        direction = "Lower / bearish bias"
    else:
        direction = "Sideways / mixed bias"
    strength = min(0.82, 0.50 + abs(score) / 300.0)
    if signals.get("pattern") in {"bullish_breakout", "bearish_breakdown"}:
        strength = min(0.88, strength + 0.05)
    if not events.get("available"):
        strength = min(strength, 0.60)
    return direction, round(strength, 2)


def _risks(m: dict[str, float], market_view: str, news: list[dict[str, Any]], events: dict[str, Any], warnings: list[str], fundamentals: dict[str, Any]) -> list[str]:
    risks = [
        "Technical levels can fail after earnings, macro shocks or gap moves.",
        "Stop-loss levels are research levels, not guaranteed execution prices.",
        "Event classification is evidence weighting, not proof that an event will move the stock in the predicted direction.",
        "Fundamental ratios can be distorted by cycles, leverage, one-off items and accounting effects; compare them with history and sector peers when available.",
    ]
    if m and m["atr"] > m["price"] * 0.04:
        risks.append("Recent volatility is high relative to price; position sizing should be conservative.")
    if "Unfavorable" in market_view:
        risks.append("The current trend context is unfavorable for long exposure.")
    if news:
        risks.append("News sentiment can change quickly and headlines may be incomplete.")
    if events.get("signals"):
        risks.append("Multiple headlines can describe the same underlying event; the model deduplicates identical titles but not all related stories.")
    if fundamentals.get("ratios", {}).get("roce_basis") == "estimated from operating margin and capital employed":
        risks.append("ROCE is estimated from public operating-margin and balance-sheet fields where a directly reported ROCE is unavailable.")
    if warnings:
        risks.append("Some requested data sources were unavailable, reducing confidence.")
    return risks


def _asdict(result: StockAnalysis) -> dict[str, Any]:
    data = asdict(result)
    data["buy_range"] = list(result.buy_range) if result.buy_range else None
    data["targets"] = list(result.targets) if result.targets else None
    data["advisory_only"] = True
    return data
