"""Build market-discovery fetchers from configured public market APIs."""
from __future__ import annotations

from typing import Any, Callable

from ..data.market_apis import AlphaVantageProvider, TwelveDataProvider
from ..data.providers import ProviderResponse


def twelve_data_universe(
    provider: TwelveDataProvider,
    *,
    market: str,
) -> Callable[[], ProviderResponse]:
    """Return a universe fetcher for US or Indian common stocks.

    The provider returns the source catalog; the scanner performs the ranking.
    """
    normalized = market.lower()
    if normalized in {"us", "usa", "united-states", "global"}:
        return lambda: provider.stocks(country="United States")
    if normalized in {"india", "in"}:
        return lambda: provider.stocks(country="India")
    raise ValueError(f"Unsupported Twelve Data market: {market}")


def alpha_vantage_universe(
    provider: AlphaVantageProvider,
    *,
    market: str,
) -> Callable[[], ProviderResponse]:
    """Return a mover-based universe fetcher for markets supported by Alpha Vantage.

    Alpha Vantage's top-gainers/losers endpoint is US-focused, so it is never
    mislabeled as an India universe. India candidates should use Twelve Data
    or another licensed India market source.
    """
    normalized = market.lower()
    if normalized not in {"us", "usa", "united-states"}:
        raise ValueError("Alpha Vantage mover discovery currently supports US equities only")

    def fetch() -> ProviderResponse:
        response = provider.top_gainers_losers()
        payload = response.payload
        if not isinstance(payload, dict):
            return response
        rows: list[dict[str, Any]] = []
        for key in ("top_gainers", "top_losers", "most_actively_traded"):
            values = payload.get(key)
            if isinstance(values, list):
                for row in values:
                    if not isinstance(row, dict):
                        continue
                    change = _float(row.get("change_percentage"))
                    volume = _float(row.get("volume"))
                    rows.append({
                        "ticker": row.get("ticker"),
                        "market": "us",
                        "name": row.get("ticker"),
                        "momentum": change,
                        "trend": change,
                        "liquidity": _liquidity_score(volume),
                        "catalyst": max(0.0, change),
                        "risk": max(0.0, -change),
                    })
        return ProviderResponse(response.provider, response.endpoint, response.fetched_at, rows, response.freshness)

    return fetch


def _float(value: Any) -> float:
    try:
        return float(str(value).replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _liquidity_score(volume: float) -> float:
    if volume <= 0:
        return 0.0
    if volume >= 50_000_000:
        return 100.0
    if volume >= 10_000_000:
        return 80.0
    if volume >= 1_000_000:
        return 60.0
    if volume >= 100_000:
        return 40.0
    return 20.0
