from __future__ import annotations
from dataclasses import dataclass
from math import sqrt
from typing import Sequence

@dataclass(frozen=True)
class TechnicalSnapshot:
    close: float; sma20: float | None; sma50: float | None; sma200: float | None; rsi14: float | None
    volatility20: float | None; momentum20: float | None; trend_score: float
    macd: float | None = None; macd_signal: float | None = None; macd_histogram: float | None = None
    bollinger_mid: float | None = None; bollinger_upper: float | None = None; bollinger_lower: float | None = None
    bollinger_position: float | None = None; atr14: float | None = None; volume_ratio20: float | None = None

def _sma(v: Sequence[float], n: int) -> float | None: return sum(v[-n:]) / n if len(v) >= n else None

def _ema(v: Sequence[float], n: int) -> float | None:
    if len(v) < n: return None
    a=2/(n+1); x=sum(v[:n])/n
    for p in v[n:]: x=a*p+(1-a)*x
    return x

def _rsi(v: Sequence[float], n: int=14) -> float | None:
    if len(v)<=n: return None
    g=[max(0.,v[i]-v[i-1]) for i in range(len(v)-n,len(v))]; l=[max(0.,v[i-1]-v[i]) for i in range(len(v)-n,len(v))]
    al=sum(l)/n
    return 100. if al==0 else 100.-100./(1.+(sum(g)/n)/al)

def _atr(h: Sequence[float], l: Sequence[float], c: Sequence[float], n:int=14) -> float | None:
    if len(c)<n+1 or not(len(h)==len(l)==len(c)): return None
    tr=[max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])) for i in range(1,len(c))]; x=sum(tr[:n])/n; a=1/n
    for p in tr[n:]: x=a*p+(1-a)*x
    return x

def snapshot(closes: Sequence[float], highs: Sequence[float]|None=None, lows: Sequence[float]|None=None, volumes: Sequence[float]|None=None) -> TechnicalSnapshot:
    if not closes: raise ValueError('closes cannot be empty')
    c=float(closes[-1]); s20,s50,s200=_sma(closes,20),_sma(closes,50),_sma(closes,200); r=_rsi(closes)
    mom=(c/closes[-21]-1) if len(closes)>=21 and closes[-21] else None
    ret=[closes[i]/closes[i-1]-1 for i in range(max(1,len(closes)-20),len(closes)) if closes[i-1]]
    vv=sqrt(sum((x-sum(ret)/len(ret))**2 for x in ret)/len(ret))*sqrt(252) if ret else None
    e12,e26=_ema(closes,12),_ema(closes,26); ml=e12-e26 if e12 is not None and e26 is not None else None
    sig=None
    if len(closes)>=35:
        ms=[_ema(closes[:i+1],12)-_ema(closes[:i+1],26) for i in range(25,len(closes))]; sig=_ema([x for x in ms if x is not None],9)
    hist=ml-sig if ml is not None and sig is not None else None
    bm=s20; sd=(sum((x-bm)**2 for x in closes[-20:])/19)**.5 if bm is not None else None
    bu=bm+2*sd if bm is not None and sd is not None else None; bl=bm-2*sd if bm is not None and sd is not None else None
    bp=(c-bl)/(bu-bl) if bu is not None and bl is not None and bu!=bl else None
    at=_atr(highs,lows,closes) if highs is not None and lows is not None else None; va=_sma(volumes,20) if volumes is not None else None
    vr=volumes[-1]/va if va else None
    parts=[]
    for s in (s20,s50,s200):
        if s: parts.append(1 if c>s else -1)
    if r is not None: parts.append(1 if 50<r<70 else -1 if r<35 or r>75 else 0)
    trend=sum(parts)/len(parts) if parts else 0.
    return TechnicalSnapshot(c,s20,s50,s200,r,vv,mom,trend,ml,sig,hist,bm,bu,bl,bp,at,vr)
