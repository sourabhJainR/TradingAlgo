from __future__ import annotations

import json
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from tradingalgo.data.sources import SourceConfig
from tradingalgo.intelligence.portfolio_connectors import (
    INDMoneyPortfolioPlugin,
    ZerodhaPortfolioPlugin,
    load_portfolio_bytes,
)
from tradingalgo.intelligence.research_suite import (
    alert_signals,
    backtest_symbol,
    portfolio_diagnostics,
    screen_analyses,
)
from tradingalgo.intelligence.technical_analytics import position_size

from .market_recommendations import asdict as market_asdict, recommend_market
from .research_service import _asdict, analyze_stock

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"


class ResearchHandler(BaseHTTPRequestHandler):
    def _send(self, status: int, content_type: str, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _json(self, status: int, payload: object) -> None:
        self._send(status, "application/json", json.dumps(payload, default=str))

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/portfolio/import":
            self._json(404, {"error": "not found"})
            return
        try:
            provider, filename, content = _multipart_upload(self)
            if provider == "indmoney":
                snapshot = INDMoneyPortfolioPlugin().import_bytes(filename, content)
            else:
                snapshot = load_portfolio_bytes(filename, content, provider="excel")
            result = _analyze_portfolio_snapshot(snapshot)
            self._json(200, result)
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
        except Exception as exc:
            self._json(500, {"error": f"portfolio import failed: {exc}"})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/api/health":
            self._send(200, "application/json", '{"status":"ok","mode":"research-only"}')
            return
        if parsed.path == "/api/analyze":
            ticker = query.get("ticker", [""])[0]
            market = query.get("market", ["US"])[0]
            horizon = query.get("horizon", ["short"])[0]
            try:
                result = analyze_stock(ticker, market, horizon)
                self._send(200, "application/json", json.dumps(_asdict(result)))
            except ValueError as exc:
                self._send(400, "application/json", json.dumps({"error": str(exc)}))
            except Exception as exc:
                self._send(500, "application/json", json.dumps({"error": f"analysis failed: {exc}"}))
            return
        if parsed.path == "/api/compare":
            try:
                tickers = _csv(query.get("tickers", [""])[0])
                market = query.get("market", ["US"])[0]
                horizon = query.get("horizon", ["short"])[0]
                if not tickers:
                    raise ValueError("tickers is required")
                if len(tickers) > 10:
                    raise ValueError("compare supports at most 10 tickers per request")
                cfg = SourceConfig.from_env()
                results = []
                for ticker in tickers:
                    try:
                        results.append(_asdict(analyze_stock(ticker, market, horizon, cfg)))
                    except Exception as exc:
                        results.append({"ticker": ticker, "error": str(exc)})
                ranked = sorted(results, key=lambda item: float(item.get("score", -101)), reverse=True)
                self._send(200, "application/json", json.dumps({"market": market, "horizon": horizon, "count": len(ranked), "results": ranked, "advisory_only": True}))
            except ValueError as exc:
                self._send(400, "application/json", json.dumps({"error": str(exc)}))
            return
        if parsed.path == "/api/risk":
            try:
                result = position_size(capital=float(query.get("capital", [""])[0]), risk_percent=float(query.get("risk_percent", ["1"])[0]), entry=float(query.get("entry", [""])[0]), stop=float(query.get("stop", [""])[0]), max_position_percent=float(query.get("max_position_percent", ["25"])[0]))
                self._send(200, "application/json", json.dumps({**result, "advisory_only": True}))
            except (ValueError, TypeError) as exc:
                self._send(400, "application/json", json.dumps({"error": str(exc)}))
            return
        if parsed.path == "/api/recommend":
            market = query.get("market", ["US"])[0]
            horizon = query.get("horizon", ["short"])[0]
            try:
                limit = int(query.get("limit", ["10"])[0])
                recommendations = int(query.get("recommendations", ["5"])[0])
                result = recommend_market(market, horizon, limit=limit, recommendations=recommendations)
                self._send(200, "application/json", json.dumps(market_asdict(result)))
            except ValueError as exc:
                self._send(400, "application/json", json.dumps({"error": str(exc)}))
            except Exception as exc:
                self._send(500, "application/json", json.dumps({"error": f"market recommendation failed: {exc}"}))
            return
        if parsed.path == "/api/screen":
            try:
                tickers = _csv(query.get("tickers", [""])[0])
                market = query.get("market", ["US"])[0]
                horizon = query.get("horizon", ["short"])[0]
                if not tickers:
                    raise ValueError("tickers is required")
                if len(tickers) > 25:
                    raise ValueError("screen supports at most 25 tickers per request")
                cfg = SourceConfig.from_env()
                analyses = []
                warnings = []
                for ticker in tickers:
                    try:
                        analyses.append(analyze_stock(ticker, market, horizon, cfg))
                    except Exception as exc:
                        warnings.append(f"{ticker}: {exc}")
                selected = screen_analyses(analyses, min_score=_float_query(query, "min_score"), min_confidence=_float_query(query, "min_confidence"), action=query.get("action", [""])[0] or None, min_rsi=_float_query(query, "min_rsi"), max_rsi=_float_query(query, "max_rsi"), max_drawdown=_float_query(query, "max_drawdown"), breakout_only=_bool_query(query, "breakout_only"))
                self._send(200, "application/json", json.dumps({"market": market, "horizon": horizon, "scanned": len(analyses), "matched": len(selected), "results": [_asdict(item) for item in selected], "warnings": warnings, "advisory_only": True}))
            except ValueError as exc:
                self._send(400, "application/json", json.dumps({"error": str(exc)}))
            except Exception as exc:
                self._send(500, "application/json", json.dumps({"error": f"screen failed: {exc}"}))
            return
        if parsed.path == "/api/backtest":
            try:
                ticker = query.get("ticker", [""])[0]
                market = query.get("market", ["US"])[0]
                strategy = query.get("strategy", ["sma_cross"])[0]
                days = int(query.get("days", ["750"])[0])
                if days < 100 or days > 5000:
                    raise ValueError("days must be between 100 and 5000")
                result = backtest_symbol(ticker, market, strategy, days)
                self._send(200, "application/json", json.dumps({**result.__dict__, "advisory_only": True, "note": "Historical simulation only; brokerage, taxes and slippage are not modeled."}))
            except ValueError as exc:
                self._send(400, "application/json", json.dumps({"error": str(exc)}))
            except Exception as exc:
                self._send(500, "application/json", json.dumps({"error": f"backtest failed: {exc}"}))
            return
        if parsed.path == "/api/portfolio":
            try:
                market = query.get("market", ["US"])[0]
                horizon = query.get("horizon", ["long"])[0]
                holdings = _weights(query.get("holdings", [""])[0])
                if not holdings:
                    raise ValueError("holdings is required, for example NVDA:30,MSFT:25,AVGO:20")
                if len(holdings) > 25:
                    raise ValueError("portfolio supports at most 25 holdings")
                cfg = SourceConfig.from_env()
                analyses = []
                warnings = []
                for ticker in holdings:
                    try:
                        analyses.append(analyze_stock(ticker, market, horizon, cfg))
                    except Exception as exc:
                        warnings.append(f"{ticker}: {exc}")
                result = portfolio_diagnostics(holdings, analyses)
                result.update({"market": market, "horizon": horizon, "warnings": warnings, "source": "manual"})
                self._send(200, "application/json", json.dumps(result))
            except ValueError as exc:
                self._send(400, "application/json", json.dumps({"error": str(exc)}))
            except Exception as exc:
                self._send(500, "application/json", json.dumps({"error": f"portfolio analysis failed: {exc}"}))
            return
        if parsed.path == "/api/portfolio/broker":
            try:
                broker = query.get("broker", [""])[0].strip().lower()
                if broker != "zerodha":
                    raise ValueError("live broker source currently supports Zerodha; use Excel/CSV for INDmoney")
                snapshot = ZerodhaPortfolioPlugin().holdings()
                self._send(200, "application/json", json.dumps(_analyze_portfolio_snapshot(snapshot)))
            except ValueError as exc:
                self._send(400, "application/json", json.dumps({"error": str(exc)}))
            except Exception as exc:
                self._send(502, "application/json", json.dumps({"error": f"broker portfolio import failed: {exc}"}))
            return
        if parsed.path == "/api/alerts":
            try:
                ticker = query.get("ticker", [""])[0]
                market = query.get("market", ["US"])[0]
                horizon = query.get("horizon", ["short"])[0]
                cfg = SourceConfig.from_env()
                analysis = analyze_stock(ticker, market, horizon, cfg)
                self._send(200, "application/json", json.dumps({"ticker": ticker.upper(), "analysis": _asdict(analysis), "alerts": alert_signals(analysis), "advisory_only": True}))
            except ValueError as exc:
                self._send(400, "application/json", json.dumps({"error": str(exc)}))
            except Exception as exc:
                self._send(500, "application/json", json.dumps({"error": f"alert analysis failed: {exc}"}))
            return
        if parsed.path == "/api/pulse":
            try:
                market = query.get("market", ["US"])[0]
                horizon = query.get("horizon", ["short"])[0]
                result = recommend_market(market, horizon, limit=25, recommendations=25)
                rows = list(result.recommendations)
                bullish = sum(item.action == "BUY" for item in rows)
                watch = sum(item.action == "WATCH" for item in rows)
                avoid = sum(item.action == "AVOID" for item in rows)
                avg_score = sum(item.score for item in rows) / len(rows) if rows else 0.0
                avg_confidence = sum(item.confidence for item in rows) / len(rows) if rows else 0.0
                breakouts = sum((item.technical_signals or {}).get("breakout_20d") == "yes" for item in rows)
                self._send(200, "application/json", json.dumps({"market": result.market, "horizon": result.horizon, "sample": len(rows), "buy": bullish, "watch": watch, "avoid": avoid, "buy_pct": round(bullish / len(rows) * 100.0, 2) if rows else 0.0, "average_score": round(avg_score, 2), "average_confidence": round(avg_confidence, 4), "breakout_count": breakouts, "provider": result.discovery_provider, "note": "Pulse is calculated from the analyzed discovery sample, not the complete exchange universe.", "advisory_only": True}))
            except Exception as exc:
                self._send(500, "application/json", json.dumps({"error": f"market pulse failed: {exc}"}))
            return
        if parsed.path in {"/", "/index.html"}:
            self._send(200, "text/html; charset=utf-8", (STATIC / "index.html").read_text(encoding="utf-8"))
            return
        if parsed.path == "/favorites":
            self._send(200, "text/html; charset=utf-8", (STATIC / "favorites.html").read_text(encoding="utf-8"))
            return
        self._send(404, "application/json", '{"error":"not found"}')

    def log_message(self, format: str, *args: object) -> None:
        return


def _multipart_upload(handler: ResearchHandler) -> tuple[str, str, bytes]:
    content_type = handler.headers.get("Content-Type", "")
    if not content_type.lower().startswith("multipart/form-data"):
        raise ValueError("portfolio import requires multipart/form-data")
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0 or length > 10 * 1024 * 1024:
        raise ValueError("portfolio upload must be between 1 byte and 10 MB")
    body = handler.rfile.read(length)
    message = BytesParser(policy=default).parsebytes(b"Content-Type: " + content_type.encode("utf-8") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body)
    provider = "excel"
    filename = ""
    content = b""
    for part in message.iter_parts():
        disposition = part.get("Content-Disposition", "")
        if "provider" in disposition and part.get_content_disposition() == "form-data":
            provider = part.get_content().strip().lower()
        if part.get_filename():
            filename = part.get_filename()
            content = part.get_payload(decode=True) or b""
    if not filename or not content:
        raise ValueError("a portfolio .xlsx, .xls or .csv file is required")
    if provider not in {"excel", "indmoney"}:
        raise ValueError("provider must be excel or indmoney")
    return provider, filename, content


def _analyze_portfolio_snapshot(snapshot: Any) -> dict[str, object]:
    if len(snapshot.positions) > 50:
        raise ValueError("portfolio supports at most 50 positions")
    market = "US" if snapshot.currency.upper() in {"USD", "USN"} else "India"
    horizon = "long"
    holdings = snapshot.weights()
    cfg = SourceConfig.from_env()
    analyses = []
    warnings = list(snapshot.warnings or [])
    for ticker in holdings:
        try:
            analyses.append(analyze_stock(ticker, market, horizon, cfg))
        except Exception as exc:
            warnings.append(f"{ticker}: {exc}")
    result = portfolio_diagnostics(holdings, analyses)
    result.update({"provider": snapshot.provider, "source": snapshot.source, "currency": snapshot.currency, "positions_imported": len(snapshot.positions), "imported_positions": [item.as_dict() for item in snapshot.positions], "market": market, "horizon": horizon, "warnings": warnings, "advisory_only": True})
    return result


def _csv(value: str) -> list[str]:
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def _weights(value: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for item in _csv(value):
        if ":" not in item:
            continue
        ticker, weight = item.split(":", 1)
        try:
            result[ticker.strip().upper()] = float(weight)
        except ValueError:
            continue
    return result


def _float_query(query: dict[str, list[str]], key: str) -> float | None:
    value = query.get(key, [""])[0]
    return float(value) if value else None


def _bool_query(query: dict[str, list[str]], key: str) -> bool:
    return query.get(key, ["false"])[0].strip().lower() in {"1", "true", "yes", "on"}


def serve(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = ThreadingHTTPServer((host, port), ResearchHandler)
    print(f"TradingAlgo research UI: http://{host}:{port}")
    print("Research only: no order execution is exposed by this server.")
    server.serve_forever()
