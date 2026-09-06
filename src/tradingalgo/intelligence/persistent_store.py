"""Persistent incremental evidence repository backed by SQLite."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from .evidence_store import evidence_key
from .models import Evidence


class SQLiteEvidenceStore:
    """Durable upsert store; unchanged evidence is not duplicated across runs."""
    def __init__(self, path: str | Path = "data/evidence.sqlite3") -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS evidence (
                evidence_key TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_name TEXT NOT NULL,
                payload TEXT NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_evidence_ticker_observed ON evidence(ticker, observed_at)")
            db.commit()

    def upsert_many(self, evidence: list[Evidence]) -> int:
        inserted_or_updated = 0
        with sqlite3.connect(self.path) as db:
            for item in evidence:
                key = evidence_key(item)
                cursor = db.execute(
                    """INSERT INTO evidence(evidence_key,ticker,observed_at,source_type,source_name,payload)
                       VALUES(?,?,?,?,?,?)
                       ON CONFLICT(evidence_key) DO UPDATE SET
                         observed_at=excluded.observed_at,
                         payload=excluded.payload""",
                    (key, item.ticker.upper(), item.observed_at.isoformat(), item.source_type.value, item.source_name, item.model_dump_json()),
                )
                inserted_or_updated += cursor.rowcount
            db.commit()
        return inserted_or_updated

    def get(self, key: str) -> Evidence | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT payload FROM evidence WHERE evidence_key=?", (key,)).fetchone()
        return Evidence.model_validate_json(row[0]) if row else None

    def list_ticker(self, ticker: str, limit: int = 500) -> list[Evidence]:
        with sqlite3.connect(self.path) as db:
            rows = db.execute(
                "SELECT payload FROM evidence WHERE ticker=? ORDER BY observed_at DESC LIMIT ?",
                (ticker.upper(), limit),
            ).fetchall()
        return [Evidence.model_validate_json(row[0]) for row in rows]
