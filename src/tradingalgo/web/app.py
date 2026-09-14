from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

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
        if parsed.path == "/api/health":
            self._send(200, "application/json", '{"status":"ok","mode":"research-only"}')
            return
        if parsed.path == "/api/analyze":
            query = parse_qs(parsed.query)
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
        if parsed.path in {"/", "/index.html"}:
            self._send(200, "text/html; charset=utf-8", (STATIC / "index.html").read_text(encoding="utf-8"))
            return
        self._send(404, "application/json", '{"error":"not found"}')

    def log_message(self, format: str, *args: object) -> None:
        return


def serve(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = ThreadingHTTPServer((host, port), ResearchHandler)
    print(f"TradingAlgo research UI: http://{host}:{port}")
    print("Research only: no broker or order execution is exposed by this server.")
    server.serve_forever()
