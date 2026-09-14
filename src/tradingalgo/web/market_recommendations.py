from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tradingalgo.data.health import ProviderHealthRegistry
from tradingalgo.data.market_apis import AlphaVantageProvider
from tradingalgo.data.sources import NsePublicSource, SourceConfig
from tradingalgo.intelligence.market_api_discovery import alpha_vantage_universe, nse_public_universe
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
    """Discover candidates, apply horizon scoring, then publish evidence-backed leaders.

    The recommendation path uses only free/public market-data routes. India
    always discovers from the public NSE universe; Alpha Vantage is used for
    US discovery when its free API key is configured.
    """
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
    if market_key == "india":
        provider = NsePublicSource()
        fetch = nse_public_universe(provider)
        provider_name = "nse-public"
    elif cfg.alpha_vantage_key:
        provider = AlphaVantageProvider(cfg.alpha_vantage_key)
        fetch = alpha_vantage_universe(provider, market="us")
        provider_name = "alpha-vantage-free-tier"
    else:
        raise RuntimeError(
            "US open-ended discovery requires ALPHAVANTAGE_API_KEY. "
            "The application uses only Alpha Vantage's free API path; no paid provider is required."
        )

    result = discovery.discover(
        fetch,
        provider=provider_name,
        market=market_key,
        limit=limit,
        horizon=horizon_key,
        min_evidence=3,
    )
    if result.errors:
        raise RuntimeError("Market discovery failed: " + "; ".join(f"{k}: {v}" for k, v in result.errors.items()))
    if not result.candidates:
        raise RuntimeError("Market discovery returned no candidates")

    analyzed: list[tuple[float, StockAnalysis]] = []
    warnings: list[str] = []
    for candidate in result.candidates:
        try:
            analysis = analyze_stock(candidate.ticker, market_key, horizon_key, cfg)
        except Exception as exc:
            warnings.append(f"{candidate.ticker}: analysis failed: {exc}")
            continue
        if len(analysis.data_sources) < MIN_EVIDENCE_SOURCES or analysis.last_price is None:
            warnings.append(f"{candidate.ticker}: excluded because evidence coverage is below the {MIN_EVIDENCE_SOURCES}-source threshold")
            continue

        # Discovery scores are already 0..100. StockAnalysis scores are -100..100,
        # so normalize them before combining the two ranking signals.
        analysis_score = max(0.0, min(100.0, (analysis.score + 100.0) / 2.0))
        final_score = candidate.score * 0.35 + analysis_score * 0.65
        ranking_score = final_score * max(0.0, min(1.0, analysis.confidence))
        analyzed.append((ranking_score, analysis))

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
        "ticker": item.ticker,
        "market": item.market,
        "horizon": item.horizon,
        "action": item.action,
        "score": item.score,
        "confidence": item.confidence,
        "last_price": item.last_price,
        "buy_range": list(item.buy_range) if item.buy_range else None,
        "stop_loss": item.stop_loss,
        "targets": list(item.targets) if item.targets else None,
        "hypothesis": item.hypothesis,
        "prediction_basis": item.prediction_basis,
        "favorable_market": item.favorable_market,
        "sector_news": item.sector_news,
        "risks": item.risks,
        "data_sources": item.data_sources,
        "warnings": item.warnings,
    }
