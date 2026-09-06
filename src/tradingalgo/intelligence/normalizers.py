from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Iterable
from .models import Evidence, Horizon, Polarity, SourceType


def _number(value: Any) -> float:
    try:
        return float(str(value).replace('%', '').replace(',', '').strip()) if value is not None else 0.0
    except ValueError:
        return 0.0


def _dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    if isinstance(value, str):
        try:
            d = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _polarity(score: float) -> Polarity:
    return Polarity.BULLISH if score > 0.15 else Polarity.BEARISH if score < -0.15 else Polarity.NEUTRAL


def normalize_quote(ticker: str, payload: dict[str, Any], source: str) -> Evidence:
    data = payload.get('Global Quote', payload)
    price = _number(data.get('05. price', data.get('c')))
    change = _number(data.get('10. change percent', data.get('dp')))
    return Evidence(id=f'{source}:quote:{ticker.upper()}', ticker=ticker.upper(), source_type=SourceType.MARKET,
        source_name=source, observed_at=datetime.now(timezone.utc), title=f'{ticker.upper()} market quote',
        summary=f'Price={price}; change_pct={change}', polarity=_polarity(change / 5),
        severity=max(-1, min(1, change / 10)), confidence=.95, novelty=.4, horizon=Horizon.INTRADAY,
        facts={'price': price, 'change_pct': change, 'raw': data})


def normalize_analyst_recommendations(ticker: str, rows: Iterable[dict[str, Any]]) -> Evidence | None:
    rows = list(rows)
    if not rows: return None
    r = rows[0]
    bullish = _number(r.get('strongBuy')) + _number(r.get('buy'))
    bearish = _number(r.get('sell')) + _number(r.get('strongSell'))
    total = bullish + _number(r.get('hold')) + bearish
    score = (bullish - bearish) / total if total else 0
    return Evidence(id=f'finnhub:analyst:{ticker.upper()}:{r.get("period", "")}', ticker=ticker.upper(),
        source_type=SourceType.ANALYST, source_name='finnhub', observed_at=datetime.now(timezone.utc),
        published_at=_dt(r.get('period')), title='Analyst recommendation trend',
        summary=f'Bullish={bullish:.0f}; bearish={bearish:.0f}; total={total:.0f}', polarity=_polarity(score),
        severity=max(-1, min(1, score)), confidence=.8, novelty=.5, horizon=Horizon.MEDIUM,
        facts={'bullish': bullish, 'bearish': bearish, 'total': total})


def normalize_news(ticker: str, rows: Iterable[dict[str, Any]], source: str = 'news') -> list[Evidence]:
    out = []
    for i, r in enumerate(rows):
        title = str(r.get('title') or r.get('headline') or 'Untitled event')
        published = _dt(r.get('published_at') or r.get('datetime') or r.get('seendate'))
        sentiment = _number(r.get('overall_sentiment_score', r.get('sentiment', 0)))
        out.append(Evidence(id=f'{source}:news:{ticker.upper()}:{i}:{published.isoformat()}', ticker=ticker.upper(),
            source_type=SourceType.NEWS, source_name=source, observed_at=datetime.now(timezone.utc),
            published_at=published, title=title, summary=str(r.get('summary') or r.get('description') or title),
            polarity=_polarity(sentiment), severity=max(-1, min(1, sentiment)), confidence=.65, novelty=.7,
            horizon=Horizon.SWING, tags=['news'], facts=r))
    return out
