from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx


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
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout

    def fetch(self, path: str, params: dict[str, Any] | None = None) -> ProviderResponse:
        url = f"{self.base_url}/{path.lstrip('/')}"
        with httpx.Client(timeout=self.timeout, headers=self.headers, follow_redirects=True) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        return ProviderResponse(
            provider=self.name,
            endpoint=str(response.url),
            fetched_at=datetime.now(timezone.utc),
            payload=payload,
        )
