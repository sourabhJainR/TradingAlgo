from __future__ import annotations
import json
from pathlib import Path
from typing import Any

class JsonEvidenceStore:
    """Dependency-free durable evidence store for the MVP; DuckDB can sit behind the same boundary later."""
    def __init__(self, path: str | Path = 'data/evidence.jsonl') -> None:
        self.path = Path(path)

    def append(self, evidence: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(evidence, default=str, separators=(',', ':')) + '\n')

    def count(self) -> int:
        if not self.path.exists(): return 0
        with self.path.open('r', encoding='utf-8') as f:
            return sum(1 for _ in f)

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        if not self.path.exists(): return []
        with self.path.open('r', encoding='utf-8') as f:
            rows = [json.loads(line) for line in f if line.strip()]
        return rows[-limit:]
