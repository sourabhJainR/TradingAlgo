"""Wire market-data APIs into the existing intelligence orchestrator contract."""
from __future__ import annotations

from typing import Callable

from ..data.market_apis import AlphaVantageProvider, TwelveDataProvider
from ..data.providers import ProviderResponse
from .orchestrator import FetchCandidate


def twelve_data_analysis_fetchers(
    provider: TwelveDataProvider,
    *,
    exchange: str | None = None,
) -> Callable[[str], dict[str, list[FetchCandidate]]]:
    """Return quote fetchers using Twelve Data without changing orchestration."""
    def fetchers(ticker: str) -> dict[str, list[FetchCandidate]]:
        return {
            "quote": [
                FetchCandidate(
                    "twelve-data",
                    lambda ticker=ticker: provider.quote(ticker, exchange=exchange),
                )
            ]
        }

    return fetchers


def alpha_vantage_analysis_fetchers(
    provider: AlphaVantageProvider,
) -> Callable[[str], dict[str, list[FetchCandidate]]]:
    """Return quote fetchers using Alpha Vantage's normalized Global Quote response."""
    def fetchers(ticker: str) -> dict[str, list[FetchCandidate]]:
        return {
            "quote": [
                FetchCandidate(
                    "alpha-vantage",
                    lambda ticker=ticker: provider.quote(ticker),
                )
            ]
        }

    return fetchers
