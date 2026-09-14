"""Provider adapters for public market-data APIs.

These adapters keep vendor-specific HTTP contracts out of the intelligence layer.
Credentials are read from environment variables; no keys are stored in the repo.
"""
from __future__ import annotations

import os
from typing import Any

from .providers import HttpProvider, ProviderResponse


class TwelveDataProvider:
    """Twelve Data adapter for global equity catalogs, movers, quotes and history."""

    def __init__(self, api_key: str | None = None, *, timeout: float = 20.0) -> None:
        key = api_key or os.getenv("TWELVE_DATA_API_KEY")
        if not key:
            raise ValueError("TWELVE_DATA_API_KEY is required")
        self._provider = HttpProvider("twelve-data", "https://api.twelvedata.com", timeout=timeout)
        self._api_key = key

    def _fetch(self, path: str, params: dict[str, Any] | None = None) -> ProviderResponse:
        request_params = dict(params or {})
        request_params["apikey"] = self._api_key
        return self._provider.fetch(path, request_params)

    def stocks(self, *, country: str | None = None, exchange: str | None = None) -> ProviderResponse:
        params: dict[str, Any] = {"type": "Common Stock", "outputsize": 5000}
        if country:
            params["country"] = country
        if exchange:
            params["exchange"] = exchange
        return self._fetch("stocks", params)

    def market_movers(self) -> ProviderResponse:
        return self._fetch("market_movers/stocks")

    def quote(self, symbol: str, *, exchange: str | None = None) -> ProviderResponse:
        params: dict[str, Any] = {"symbol": symbol}
        if exchange:
            params["exchange"] = exchange
        return self._fetch("quote", params)

    def time_series(self, symbol: str, *, interval: str = "1day", outputsize: int = 500,
                    exchange: str | None = None) -> ProviderResponse:
        params: dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "outputsize": outputsize,
            "adjust": "all",
        }
        if exchange:
            params["exchange"] = exchange
        return self._fetch("time_series", params)


class AlphaVantageProvider:
    """Alpha Vantage adapter for global equities and fundamental data."""

    def __init__(self, api_key: str | None = None, *, timeout: float = 20.0) -> None:
        key = api_key or os.getenv("ALPHAVANTAGE_API_KEY")
        if not key:
            raise ValueError("ALPHAVANTAGE_API_KEY is required")
        self._provider = HttpProvider("alpha-vantage", "https://www.alphavantage.co", timeout=timeout)
        self._api_key = key

    def _fetch(self, function: str, **params: Any) -> ProviderResponse:
        request_params = {"function": function, **params, "apikey": self._api_key}
        return self._provider.fetch("query", request_params)

    def daily(self, symbol: str, *, adjusted: bool = True, outputsize: str = "compact") -> ProviderResponse:
        function = "TIME_SERIES_DAILY_ADJUSTED" if adjusted else "TIME_SERIES_DAILY"
        return self._fetch(function, symbol=symbol, outputsize=outputsize)

    def quote(self, symbol: str) -> ProviderResponse:
        return self._fetch("GLOBAL_QUOTE", symbol=symbol)

    def overview(self, symbol: str) -> ProviderResponse:
        return self._fetch("OVERVIEW", symbol=symbol)

    def earnings_estimates(self, symbol: str) -> ProviderResponse:
        return self._fetch("EARNINGS_ESTIMATES", symbol=symbol)

    def top_gainers_losers(self) -> ProviderResponse:
        return self._fetch("TOP_GAINERS_LOSERS")

    def market_status(self) -> ProviderResponse:
        return self._fetch("MARKET_STATUS")
