"""Build market-discovery fetchers from free/public market APIs."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from ..data.market_apis import AlphaVantageProvider
from ..data.providers import ProviderResponse
from ..data.sources import NsePublicSource


def twelve_data_universe(provider: Any, *, market: str) -> Callable[[], ProviderResponse]:
    """Compatibility adapter retained for legacy callers; not used by recommendations."""
    normalized = market.lower()
    if normalized in {"us", "usa", "united-states", "global"}:
        return lambda: provider.stocks(country="United States")
    if normalized in {"india", "in"}:
        return lambda: provider.stocks(country="India")
    raise ValueError(f"Unsupported Twelve Data market: {market}")


def nse_public_universe(provider: NsePublicSource, *, index: str = "NIFTY 500") -> Callable[[], ProviderResponse]:
    """Return a free NSE universe enriched with sector-relative and regime factors."""
    def fetch() -> ProviderResponse:
        response = provider.universe(index=index)
        payload = response.payload
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        clean = [row for row in rows if isinstance(row, dict) and row.get("symbol")]
        sector_returns: dict[str, list[float]] = defaultdict(list)
        market_returns: list[float] = []
        for row in clean:
            change = _float(row.get("pChange") or row.get("perChange30d"))
            market_returns.append(change)
            sector = _sector(row)
            if sector:
                sector_returns[sector].append(change)
        breadth = sum(1 for value in market_returns if value > 0) / max(1, len(market_returns))
        median_market = _median(market_returns)
        regime = max(0.0, min(100.0, 50.0 + median_market * 3.0 + (breadth - 0.5) * 60.0))
        normalized: list[dict[str, Any]] = []
        for row in clean:
            change = _float(row.get("pChange") or row.get("perChange30d"))
            sector = _sector(row)
            sector_avg = _median(sector_returns.get(sector, [])) if sector else median_market
            relative = max(0.0, min(100.0, 50.0 + (change - sector_avg) * 4.0))
            volume = _float(row.get("totalTradedVolume") or row.get("totalTradedValue"))
            price = _float(row.get("lastPrice"))
            normalized.append({
                "ticker": row.get("symbol"), "market": "india",
                "name": (row.get("meta") or {}).get("companyName") or row.get("symbol"),
                "price": price, "volume": volume, "dollar_volume": volume * price,
                "momentum": change, "trend": _trend_score(row), "sector": sector,
                "sector_relative_strength": relative, "market_regime": regime,
                "liquidity": _liquidity_score(volume), "evidence_count": 5,
            })
        return ProviderResponse(response.provider, response.endpoint, response.fetched_at, normalized, response.freshness)
    return fetch


def alpha_vantage_universe(provider: AlphaVantageProvider, *, market: str) -> Callable[[], ProviderResponse]:
    """Return a free Alpha Vantage US mover universe."""
    if market.lower() not in {"us", "usa", "united-states"}:
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
                    if not isinstance(row, dict) or not row.get("ticker"):
                        continue
                    change = _float(row.get("change_percentage"))
                    volume = _float(row.get("volume"))
                    price = _float(row.get("price"))
                    rows.append({
                        "ticker": row.get("ticker"), "market": "us", "name": row.get("ticker"),
                        "price": price, "volume": volume, "dollar_volume": price * volume,
                        "momentum": change, "trend": 50.0 + change * 2.5,
                        "relative_strength": 50.0 + change * 2.0, "market_regime": 50.0,
                        "liquidity": _liquidity_score(volume), "catalyst": max(0.0, change),
                        "risk": max(0.0, -change), "evidence_count": 5,
                    })
        return ProviderResponse(response.provider, response.endpoint, response.fetched_at, rows, response.freshness)
    return fetch


def _sector(row: dict[str, Any]) -> str:
    meta = row.get("meta")
    if isinstance(meta, dict):
        return str(meta.get("industry") or meta.get("sector") or "").strip()
    return str(row.get("industry") or row.get("sector") or "").strip()


def _trend_score(row: dict[str, Any]) -> float:
    value = _float(row.get("perChange30d") or row.get("pChange"))
    return max(0.0, min(100.0, 50.0 + value * 2.5))


def _float(value: Any) -> float:
    try:
        return float(str(value).replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2.0


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
