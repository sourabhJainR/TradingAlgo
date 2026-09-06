from tradingalgo.intelligence.normalizers import normalize_analyst_recommendations, normalize_quote, normalize_news
from tradingalgo.intelligence.technical import snapshot


def test_quote_normalization():
    e = normalize_quote('NVDA', {'Global Quote': {'05. price': '100', '10. change percent': '2.0%'}}, 'alpha_vantage')
    assert e.ticker == 'NVDA' and e.facts['price'] == 100


def test_analyst_normalization():
    e = normalize_analyst_recommendations('NVDA', [{'period': '2026-09-01', 'strongBuy': 10, 'buy': 20, 'hold': 5, 'sell': 2, 'strongSell': 1}])
    assert e is not None and e.polarity.value == 'bullish'


def test_news_normalization():
    out = normalize_news('NVDA', [{'title': 'Positive catalyst', 'overall_sentiment_score': 0.6, 'datetime': 1756684800}], 'alpha_vantage_news')
    assert len(out) == 1 and out[0].ticker == 'NVDA'


def test_technical_snapshot():
    closes = [float(i) for i in range(1, 221)]
    t = snapshot(closes)
    assert t.sma20 is not None and t.sma200 is not None and t.rsi14 == 100
