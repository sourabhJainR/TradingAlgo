"""Optional analytical history backed by DuckDB with Polars interoperability."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import Evidence


class AnalyticalHistory:
    """Persist/query evidence history without making DuckDB/Polars runtime-mandatory."""

    def __init__(self, path: str | Path = "data/tradingalgo.duckdb") -> None:
        try:
            import duckdb
        except ImportError as exc:
            raise RuntimeError("Install the research extras: pip install 'tradingalgo[research]'") from exc
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = duckdb.connect(self.path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS evidence_history (
            evidence_key VARCHAR PRIMARY KEY, ticker VARCHAR, source_type VARCHAR,
            source_name VARCHAR, observed_at TIMESTAMPTZ, published_at TIMESTAMPTZ,
            title VARCHAR, summary VARCHAR, polarity VARCHAR, severity DOUBLE,
            confidence DOUBLE, novelty DOUBLE, horizon VARCHAR, tags VARCHAR, facts VARCHAR
        )""")

    def upsert(self, evidence: Iterable[Evidence]) -> int:
        rows = list(evidence)
        for item in rows:
            self.db.execute("""INSERT OR REPLACE INTO evidence_history VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
                item.id, item.ticker.upper(), item.source_type.value, item.source_name,
                item.observed_at.astimezone(timezone.utc),
                item.published_at.astimezone(timezone.utc) if item.published_at else None,
                item.title, item.summary, item.polarity.value, item.severity,
                item.confidence, item.novelty, item.horizon.value,
                ",".join(item.tags), str(item.facts)))
        return len(rows)

    def query_polars(self, sql: str):
        try:
            import polars as pl
        except ImportError as exc:
            raise RuntimeError("Install the research extras: pip install 'tradingalgo[research]'") from exc
        return pl.from_arrow(self.db.execute(sql).fetch_arrow_table())

    def close(self) -> None:
        self.db.close()
