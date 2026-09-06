"""Canonical evidence and advisory-domain models.

The intelligence layer deliberately separates facts from derived signals and
recommendations. Every material signal can carry provenance and freshness.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    MARKET = "market"
    FUNDAMENTAL = "fundamental"
    SEC_FILING = "sec_filing"
    COMPANY_FILING = "company_filing"
    ANALYST = "analyst"
    NEWS = "news"
    SOCIAL = "social"
    MACRO = "macro"
    GEOPOLITICAL = "geopolitical"
    LEGAL = "legal"
    M_AND_A = "m_and_a"
    ORDER_BOOK = "order_book"
    ALTERNATIVE = "alternative"


class Polarity(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class Horizon(StrEnum):
    INTRADAY = "intraday"
    SWING = "days_to_weeks"
    MEDIUM = "weeks_to_months"
    LONG = "months_to_years"


class Evidence(BaseModel):
    id: str
    ticker: str
    source_type: SourceType
    source_name: str
    source_url: str | None = None
    observed_at: datetime
    published_at: datetime | None = None
    expires_at: datetime | None = None
    title: str
    summary: str
    polarity: Polarity = Polarity.NEUTRAL
    severity: float = Field(default=0.0, ge=-1.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    novelty: float = Field(default=0.5, ge=0.0, le=1.0)
    horizon: Horizon = Horizon.MEDIUM
    tags: list[str] = Field(default_factory=list)
    facts: dict[str, Any] = Field(default_factory=dict)

    @property
    def freshness(self) -> float:
        now = datetime.now(timezone.utc)
        age_hours = max(0.0, (now - self.observed_at.astimezone(timezone.utc)).total_seconds() / 3600)
        return max(0.0, 1.0 - age_hours / 720.0)


class Signal(BaseModel):
    name: str
    category: str
    ticker: str
    score: float = Field(ge=-100.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    horizon: Horizon
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    features: dict[str, float] = Field(default_factory=dict)


class Advisory(BaseModel):
    ticker: str
    action: str
    score: float = Field(ge=-100.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    horizon: Horizon
    bull_case: list[str] = Field(default_factory=list)
    bear_case: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    catalysts: list[str] = Field(default_factory=list)
    signals: list[Signal] = Field(default_factory=list)
    data_quality: float = Field(default=0.0, ge=0.0, le=1.0)
