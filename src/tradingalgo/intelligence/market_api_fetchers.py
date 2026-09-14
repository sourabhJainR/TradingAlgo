"""Wire market-data APIs into the existing intelligence orchestrator contract."""
from __future__ import annotations

from typing import Callable

from ..data.market_apis import AlphaVantageProvider, TwelveDataProvider
from .orchestrator import FetchCandidate


def twelve_data_analysis_fetchers(
    provider: TwelveDataProvider,
    *,
    exchange: str | None = None,
) -> Callable[[str], dict[str, list[FetchCandidate]]]:
    """Return quote and history fetchers using Twelve Data."""
    def fetchers(ticker: str) -> dict[str, list[FetchCandidate]]:
        return {
            "quote": [FetchCandidate("twelve-data", lambda ticker=ticker: provider.quote(ticker, exchange=exchange))],
            "history": [FetchCandidate("twelve-data", lambda ticker=ticker: provider.time_series(ticker, outputsize=250, exchange=exchange))],
        }
    return fetchers


def alpha_vantage_analysis_fetchers(
    provider: AlphaVantageProvider,
) -> Callable[[str], dict[str, list[FetchCandidate]]]:
    """Return quote and history fetchers using Alpha Vantage."""
    def fetchers(ticker: str) -> dict[str, list[FetchCandidate]]:
        return {
            "quote": [FetchCandidate("alpha-vantage", lambda ticker=ticker: provider.quote(ticker))],
            "history": [FetchCandidate("alpha-vantage", lambda ticker=ticker: provider.daily(ticker, adjusted=True, outputsize="compact"))],
        }
    return fetchers
