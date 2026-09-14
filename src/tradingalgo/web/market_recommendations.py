from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tradingalgo.data.health import ProviderHealthRegistry
from tradingalgo.data.market_apis import AlphaVantageProvider, TwelveDataProvider
from tradingalgo.data.sources import SourceConfig
from tradingalgo.intelligence.market_api_discovery import alpha_vantage_universe, twelve_data_universe
from tradingalgo.intelligence.market_scanner import MarketDiscovery

from .research_service import StockAnalysis, analyze_stock

MIN_EVIDENCE_SOURCES = 2


@dataclass(frozen=True)
class MarketRecommendations:
    market: str
    horizon: str
    candidates_scanned: int
    candidates_analyzed: int
    recommendations: tuple[StockAnalysis, ...]
    discovery_provider: str
    warnings: tuple[str, ...]


def recommend_market(
    market: str,
    horizon: str,
    *,
    limit: int = 10,
    recommendations: int = 5,
    config: SourceConfig | None = None,
) -> MarketRecommendations:
    """Discover candidates, apply horizon scoring, then publish evidence-backed leaders."""
    if limit < 1 or recommendations < 1 or recommendations > limit:
        raise ValueError("limit and recommendations must be positive, with recommendations <= limit")
    market_key = market.strip().lower()
    horizon_key = horizon.strip().lower()
    if market_key not in {"us", "india"}:
        raise ValueError("market must be US or India")
    if horizon_key not in {"short", "long"}:
        raise ValueError("horizon must be short or long")

    cfg = config or SourceConfig.from_env()
    discovery = MarketDiscovery(ProviderHealthRegistry())
    warnings: list[str] = []
    if cfg.twelve_data_key:
        provider = TwelveDataProvider(cfg.twelve_data_key)
        fetch = twelve_data_universe(provider, market=market_key)
        provider_name = "twelve-data"
    elif cfg.alpha_vantage_key and market_key == "us":
        provider = AlphaVantageProvider(cfg.alpha_vantage_key)
        fetch = alpha_vantage_universe(provider, market=market_key)
        provider_name = "alpha-vantage"
    else:
        raise RuntimeError("Open-ended discovery requires TWELVE_DATA_API_KEY, or ALPHAVANTAGE_API_KEY for US discovery")

    result = discovery.discover(
        fetch,
        provider=provider_name,
        market=market_key,
        limit=limit,
        horizon=horizon_key,
    )
    if result.errors:
        raise RuntimeError("Market discovery failed: " + "; ".join(f"{k}: {v}" for k, v in result.errors.items()))
    if not result.candidates:
        raise RuntimeError("Market discovery returned no candidates")

    analyzed: list[tuple[float, StockAnalysis]] = []
    for candidate in result.candidates:
        try:
            analysis = analyze_stock(candidate.ticker, market_key, horizon_key, cfg)
        except Exception as exc:
            warnings.append(f"{candidate.ticker}: analysis failed: {exc}")
            continue
        if len(analysis.data_sources) < MIN_EVIDENCE_SOURCES or analysis.last_price is None:
            warnings.append(
                f"{candidate.ticker}: excluded because evidence coverage is below "
                f"the {MIN_EVIDENCE_SOURCES}-source threshold"
            )
            continue
        # The final publication score combines the horizon-specific discovery
        # shortlist with the fully analyzed stock score and confidence.
        final_score = candidate.score * 0.35 + analysis.score * 0.65
        analyzed.append((final_score * analysis.confidence, analysis))

    analyzed.sort(key=lambda item: (item[0], item[1].ticker), reverse=True)
    return MarketRecommendations(
        market="US" if market_key == "us" else "India",
        horizon="Short term" if horizon_key == "short" else "Long term",
        candidates_scanned=len(result.candidates),
        candidates_analyzed=len(analyzed),
        recommendations=tuple(item[1] for item in analyzed[:recommendations]),
        discovery_provider=provider_name,
        warnings=tuple(warnings),
    )


def asdict(result: MarketRecommendations) -> dict[str, Any]:
    return {
        "market": result.market,
        "horizon": result.horizon,
        "candidates_scanned": result.candidates_scanned,
        "candidates_analyzed": result.candidates_analyzed,
        "discovery_provider": result.discovery_provider,
        "minimum_evidence_sources": MIN_EVIDENCE_SOURCES,
        "recommendations": [_stock_dict(item) for item in result.recommendations],
        "warnings": list(result.warnings),
        "advisory_only": True,
    }


def _stock_dict(item: StockAnalysis) -> dict[str, Any]:
    return {
        "ticker": item.ticker, "market": item.market, "horizon": item.horizon,
        "action": item.action, "score": item.score, "confidence": item.confidence,
        "last_price": item.last_price,
        "buy_range": list(item.buy_range) if item.buy_range else None,
        "stop_loss": item.stop_loss, "targets": list(item.targets) if item.targets else None,
        "hypothesis": item.hypothesis, "prediction_basis": item.prediction_basis,
        "favorable_market": item.favorable_market, "sector_news": item.sector_news,
        "risks": item.risks, "data_sources": item.data_sources, "warnings": item.warnings,
    }
