"""Evidence, signal, orchestration and advisory intelligence."""

from .composer import compose_advisory, evidence_signals
from .market_api_discovery import alpha_vantage_universe, twelve_data_universe
from .market_api_fetchers import alpha_vantage_analysis_fetchers, twelve_data_analysis_fetchers
from .market_scanner import DiscoveryResult, MarketCandidate, MarketDiscovery
from .orchestrator import (
    FetchCandidate,
    IntelligenceOrchestrator,
    MarketRecommendation,
    MarketRecommendationResult,
    OrchestrationResult,
)
from .trade_plan import TradePlan, build_trade_plan, candles_from_provider

__all__ = [
    "DiscoveryResult",
    "FetchCandidate",
    "IntelligenceOrchestrator",
    "MarketCandidate",
    "MarketDiscovery",
    "MarketRecommendation",
    "MarketRecommendationResult",
    "OrchestrationResult",
    "TradePlan",
    "alpha_vantage_analysis_fetchers",
    "alpha_vantage_universe",
    "build_trade_plan",
    "candles_from_provider",
    "compose_advisory",
    "evidence_signals",
    "twelve_data_analysis_fetchers",
    "twelve_data_universe",
]
