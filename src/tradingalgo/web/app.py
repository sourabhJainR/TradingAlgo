from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from tradingalgo.data.sources import SourceConfig
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
                self._send(200, "application/json", json.dumps({
                    "market": market,
                    "horizon": horizon,
                    "count": len(ranked),
                    "results": ranked,
                    "advisory_only": True,
                }))
            except ValueError as exc:
                self._send(400, "application/json", json.dumps({"error": str(exc)}))
            return
        if parsed.path == "/api/risk":
            try:
                result = position_size(
                    capital=float(query.get("capital", [""])[0]),
                    risk_percent=float(query.get("risk_percent", ["1"])[0]),
                    entry=float(query.get("entry", [""])[0]),
                    stop=float(query.get("stop", [""])[0]),
                    max_position_percent=float(query.get("max_position_percent", ["25"])[0]),
                )
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
        if parsed.path in {"/", "/index.html"}:
            self._send(200, "text/html; charset=utf-8", (STATIC / "index.html").read_text(encoding="utf-8"))
            return
        self._send(404, "application/json", '{"error":"not found"}')

    def log_message(self, format: str, *args: object) -> None:
        return


def _csv(value: str) -> list[str]:
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def serve(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = ThreadingHTTPServer((host, port), ResearchHandler)
    print(f"TradingAlgo research UI: http://{host}:{port}")
    print("Research only: no broker or order execution is exposed by this server.")
    server.serve_forever()
