# Favorites and sector watchlist

TradingAlgo now includes a lightweight `/favorites` workspace for personal research tracking.

## What it supports

- Favorite stocks with market and research horizon.
- Favorite sectors/themes as research groups.
- Remove favorites without touching portfolio data.
- Refresh a favorite stock through the existing `/api/analyze` advisory engine.
- See action, price, score, confidence, buy range, stop and targets in the watchlist.
- Browser-local persistence through `localStorage`; no account, database or paid service is required.

## Design boundary

Favorites are not positions. They are research candidates. Portfolio data remains in the existing portfolio workflow.

Sector favorites are intentionally labels/groups rather than fabricated sector scores. Representative stocks can be added to the stock list for analysis.

The next natural extensions are named watchlists, thesis notes, review dates, condition-based alerts, and automatic thesis-change detection.
