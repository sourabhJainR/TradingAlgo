"""Evidence, signal, orchestration and advisory intelligence."""

from .composer import compose_advisory, evidence_signals
from .market_scanner import DiscoveryResult, MarketCandidate, MarketDiscovery
from .orchestrator import (
    FetchCandidate,
    IntelligenceOrchestrator,
    MarketRecommendation,
    MarketRecommendationResult,
    OrchestrationResult,
)

__all__ = [
    "DiscoveryResult",
    "FetchCandidate",
    "IntelligenceOrchestrator",
    "MarketCandidate",
    "MarketDiscovery",
    "MarketRecommendation",
    "MarketRecommendationResult",
    "OrchestrationResult",
    "compose_advisory",
    "evidence_signals",
]
