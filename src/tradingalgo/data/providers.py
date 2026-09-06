from __future__ import annotations

import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx

from tradingalgo.data.health import ProviderHealthRegistry


@dataclass(frozen=True)
class ProviderResponse:
    provider: str
    endpoint: str
    fetched_at: datetime
    payload: Any
    freshness: str = "unknown"


class DataProvider(Protocol):
    name: str

    def fetch(self, path: str, params: dict[str, Any] | None = None) -> ProviderResponse: ...


class HttpProvider:
    def __init__(
        self,
        name: str,
        base_url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 20.0,
        max_retries: int = 2,
        health: ProviderHealthRegistry | None = None,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.health = health or ProviderHealthRegistry()

    def fetch(self, path: str, params: dict[str, Any] | None = None) -> ProviderResponse:
        url = f"{self.base_url}/{path.lstrip('/')}"
        last_error: Exception | None = None
        retryable = {429, 500, 502, 503, 504}
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout, headers=self.headers, follow_redirects=True) as client:
                    response = client.get(url, params=params)
                if response.status_code in retryable and attempt < self.max_retries:
                    time.sleep((0.25 * (2**attempt)) + random.uniform(0, 0.1))
                    continue
                response.raise_for_status()
                payload = response.json()
                self.health.record_success(self.name)
                return ProviderResponse(
                    provider=self.name,
                    endpoint=str(response.url),
                    fetched_at=datetime.now(timezone.utc),
                    payload=payload,
                )
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt < self.max_retries and isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
                    time.sleep((0.25 * (2**attempt)) + random.uniform(0, 0.1))
                    continue
                self.health.record_failure(self.name)
                raise
        self.health.record_failure(self.name)
        raise RuntimeError(f"Provider {self.name} failed") from last_error
