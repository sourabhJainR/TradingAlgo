from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .providers import HttpProvider, ProviderResponse


@dataclass(frozen=True)
class SourceConfig:
    alpha_vantage_key: str | None = None
    finnhub_key: str | None = None
    fred_key: str | None = None
    sec_user_agent: str = "TradingAlgo research contact: configured-by-user"

    @classmethod
    def from_env(cls) -> "SourceConfig":
        return cls(
            alpha_vantage_key=os.getenv("ALPHAVANTAGE_API_KEY"),
            finnhub_key=os.getenv("FINNHUB_API_KEY"),
            fred_key=os.getenv("FRED_API_KEY"),
            sec_user_agent=os.getenv(
                "SEC_USER_AGENT", "TradingAlgo research contact: configured-by-user"
            ),
        )


class AlphaVantageSource:
    name = "alpha_vantage"

    def __init__(self, config: SourceConfig) -> None:
        self.config = config
        self.provider = HttpProvider(self.name, "https://www.alphavantage.co")

    def _call(self, function: str, **params: Any) -> ProviderResponse:
        if not self.config.alpha_vantage_key:
            raise RuntimeError("ALPHAVANTAGE_API_KEY is not configured")
        params.update(function=function, apikey=self.config.alpha_vantage_key)
        return self.provider.fetch("query", params)

    def quote(self, symbol: str) -> ProviderResponse:
        return self._call("GLOBAL_QUOTE", symbol=symbol)

    def daily(self, symbol: str, outputsize: str = "compact") -> ProviderResponse:
        return self._call("TIME_SERIES_DAILY", symbol=symbol, outputsize=outputsize)

    def technical(self, function: str, symbol: str, interval: str = "daily", **params: Any) -> ProviderResponse:
        return self._call(function, symbol=symbol, interval=interval, **params)

    def news_sentiment(self, tickers: str | None = None, limit: int = 50) -> ProviderResponse:
        params: dict[str, Any] = {"limit": limit, "sort": "LATEST"}
        if tickers:
            params["tickers"] = tickers
        return self._call("NEWS_SENTIMENT", **params)


class FinnhubSource:
    name = "finnhub"

    def __init__(self, config: SourceConfig) -> None:
        self.config = config
        self.provider = HttpProvider(self.name, "https://finnhub.io/api/v1")

    def _call(self, path: str, **params: Any) -> ProviderResponse:
        if not self.config.finnhub_key:
            raise RuntimeError("FINNHUB_API_KEY is not configured")
        params["token"] = self.config.finnhub_key
        return self.provider.fetch(path, params)

    def quote(self, symbol: str) -> ProviderResponse:
        return self._call("quote", symbol=symbol)

    def recommendation_trends(self, symbol: str) -> ProviderResponse:
        return self._call("stock/recommendation", symbol=symbol)

    def price_target(self, symbol: str) -> ProviderResponse:
        return self._call("stock/price-target", symbol=symbol)

    def upgrades_downgrades(self, symbol: str) -> ProviderResponse:
        return self._call("stock/upgrade-downgrade", symbol=symbol)

    def news(self, symbol: str, from_date: str, to_date: str) -> ProviderResponse:
        return self._call("company-news", symbol=symbol, _from=from_date, to=to_date)


class SecSource:
    name = "sec_edgar"

    def __init__(self, config: SourceConfig) -> None:
        self.provider = HttpProvider(
            self.name,
            "https://data.sec.gov",
            headers={"User-Agent": config.sec_user_agent, "Accept-Encoding": "gzip, deflate"},
        )

    def submissions(self, cik: str) -> ProviderResponse:
        return self.provider.fetch(f"submissions/CIK{cik.zfill(10)}.json")

    def companyfacts(self, cik: str) -> ProviderResponse:
        return self.provider.fetch(f"api/xbrl/companyfacts/CIK{cik.zfill(10)}.json")


class FredSource:
    name = "fred"

    def __init__(self, config: SourceConfig) -> None:
        self.config = config
        self.provider = HttpProvider(self.name, "https://api.stlouisfed.org/fred")

    def observations(self, series_id: str, **params: Any) -> ProviderResponse:
        if not self.config.fred_key:
            raise RuntimeError("FRED_API_KEY is not configured")
        params.update(series_id=series_id, api_key=self.config.fred_key, file_type="json")
        return self.provider.fetch("series/observations", params)


class GdeltSource:
    name = "gdelt"

    def __init__(self) -> None:
        self.provider = HttpProvider(self.name, "https://api.gdeltproject.org/api/v2")

    def news(self, query: str, max_records: int = 50) -> ProviderResponse:
        return self.provider.fetch(
            "doc/doc",
            {
                "query": query,
                "mode": "artlist",
                "format": "json",
                "maxrecords": max_records,
                "sort": "datedesc",
            },
        )
