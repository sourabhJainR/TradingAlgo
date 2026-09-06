from __future__ import annotations
from .models import Horizon, Signal
from .technical import TechnicalSnapshot

def build_technical_signal(ticker: str, snapshot: TechnicalSnapshot) -> Signal:
    score = 0.0; reasons: list[str] = []
    for value, weight, label in ((snapshot.sma20,15,'SMA20'),(snapshot.sma50,20,'SMA50'),(snapshot.sma200,30,'SMA200')):
        if value is not None: score += weight if snapshot.close > value else -weight; reasons.append(f"above {label}" if snapshot.close > value else f"below {label}")
    if snapshot.rsi14 is not None:
        if 50 <= snapshot.rsi14 <= 70: score += 15; reasons.append('RSI confirms positive momentum')
        elif snapshot.rsi14 < 35: score += 5; reasons.append('RSI is oversold')
        elif snapshot.rsi14 > 75: score -= 10; reasons.append('RSI is overbought')
    if snapshot.momentum20 is not None: score += 20 if snapshot.momentum20 > 0 else -20; reasons.append('positive 20-day momentum' if snapshot.momentum20 > 0 else 'negative 20-day momentum')
    if snapshot.macd_histogram is not None: score += 10 if snapshot.macd_histogram > 0 else -10; reasons.append('MACD histogram positive' if snapshot.macd_histogram > 0 else 'MACD histogram negative')
    if snapshot.bollinger_position is not None:
        if snapshot.bollinger_position > 0.8: score -= 5; reasons.append('near upper Bollinger band')
        elif snapshot.bollinger_position < 0.2: score += 5; reasons.append('near lower Bollinger band')
    if snapshot.volume_ratio20 is not None and snapshot.volume_ratio20 >= 1.5:
        score += 5 if (snapshot.momentum20 or 0) > 0 else -5; reasons.append('elevated volume confirms price direction')
    score = max(-100., min(100., score)); polarity='bullish' if score>10 else 'bearish' if score<-10 else 'neutral'
    return Signal(name='technical_trend',category='technical',ticker=ticker.upper(),score=score,
        confidence=min(.95,.35+.12*len(reasons)),horizon=Horizon.SWING,
        rationale=f'Technical structure is {polarity}: ' + '; '.join(reasons),evidence_ids=[],
        features={'trend_score':snapshot.trend_score,'rsi14':snapshot.rsi14 or 0.,'momentum20':snapshot.momentum20 or 0.,'volatility20':snapshot.volatility20 or 0.,'macd':snapshot.macd or 0.,'macd_signal':snapshot.macd_signal or 0.,'macd_histogram':snapshot.macd_histogram or 0.,'bollinger_position':snapshot.bollinger_position or 0.,'atr14':snapshot.atr14 or 0.,'volume_ratio20':snapshot.volume_ratio20 or 0.})
