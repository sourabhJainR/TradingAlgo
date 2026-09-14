from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO
import os
from pathlib import Path
from typing import Any

import httpx
import pandas as pd


@dataclass(frozen=True)
class PortfolioPosition:
    ticker: str
    quantity: float
    average_price: float | None = None
    last_price: float | None = None
    invested_value: float | None = None
    current_value: float | None = None
    pnl: float | None = None
    pnl_pct: float | None = None
    broker: str = "import"
    asset_class: str = "equity"

    def value(self) -> float:
        if self.current_value is not None:
            return max(0.0, float(self.current_value))
        if self.last_price is not None:
            return max(0.0, float(self.last_price) * float(self.quantity))
        if self.invested_value is not None:
            return max(0.0, float(self.invested_value))
        if self.average_price is not None:
            return max(0.0, float(self.average_price) * float(self.quantity))
        return 0.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PortfolioSnapshot:
    provider: str
    positions: list[PortfolioPosition]
    currency: str = "INR"
    source: str = "import"
    warnings: list[str] | None = None

    def weights(self) -> dict[str, float]:
        values = {item.ticker.upper(): item.value() for item in self.positions}
        total = sum(values.values())
        if total <= 0:
            raise ValueError("portfolio import contains no positions with a usable value")
        return {ticker: value / total * 100.0 for ticker, value in values.items() if value > 0}

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "currency": self.currency,
            "source": self.source,
            "positions": [item.as_dict() for item in self.positions],
            "warnings": self.warnings or [],
        }


_ALIASES: dict[str, tuple[str, ...]] = {
    "ticker": ("ticker", "symbol", "stock", "scrip", "security", "security name", "instrument"),
    "quantity": ("quantity", "qty", "units", "shares"),
    "average_price": ("average price", "avg price", "buy price", "average cost", "avg cost"),
    "last_price": ("last price", "ltp", "current price", "market price", "price"),
    "invested_value": ("invested value", "invested amount", "buy value", "cost value", "cost"),
    "current_value": ("current value", "market value", "present value", "value", "valuation"),
    "pnl": ("p&l", "pnl", "profit/loss", "profit loss", "gain/loss", "gain loss"),
    "pnl_pct": ("p&l %", "pnl %", "pnl percent", "return %", "gain %"),
    "asset_class": ("asset class", "asset type", "type", "category"),
    "currency": ("currency", "ccy"),
}


def _norm_name(value: Any) -> str:
    return " ".join(str(value).strip().lower().replace("_", " ").split())


def _find_columns(columns: list[Any], aliases: tuple[str, ...]) -> list[Any]:
    normalized = [(_norm_name(column), column) for column in columns]
    found: list[Any] = []
    for alias in aliases:
        found.extend(column for name, column in normalized if name == alias and column not in found)
    return found


def _number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip().replace(",", "").replace("₹", "").replace("$", "")
    if text.endswith("%"):
        text = text[:-1]
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _row_text(row: pd.Series, columns: list[Any], default: str = "") -> str:
    for column in columns:
        value = row.get(column)
        if value is not None and not pd.isna(value) and str(value).strip():
            return str(value).strip()
    return default


def _row_number(row: pd.Series, columns: list[Any]) -> float | None:
    for column in columns:
        value = _number(row.get(column))
        if value is not None:
            return value
    return None


def positions_from_dataframe(frame: pd.DataFrame, provider: str = "excel") -> PortfolioSnapshot:
    if frame.empty:
        raise ValueError("portfolio spreadsheet is empty")
    columns = list(frame.columns)
    ticker_cols = _find_columns(columns, _ALIASES["ticker"])
    if not ticker_cols:
        raise ValueError("portfolio spreadsheet needs a ticker/symbol/security column")
    quantity_cols = _find_columns(columns, _ALIASES["quantity"])
    avg_cols = _find_columns(columns, _ALIASES["average_price"])
    last_cols = _find_columns(columns, _ALIASES["last_price"])
    invested_cols = _find_columns(columns, _ALIASES["invested_value"])
    current_cols = _find_columns(columns, _ALIASES["current_value"])
    pnl_cols = _find_columns(columns, _ALIASES["pnl"])
    pnl_pct_cols = _find_columns(columns, _ALIASES["pnl_pct"])
    asset_cols = _find_columns(columns, _ALIASES["asset_class"])
    currency_cols = _find_columns(columns, _ALIASES["currency"])

    positions: list[PortfolioPosition] = []
    warnings: list[str] = []
    for row_number, row in frame.iterrows():
        ticker = _row_text(row, ticker_cols).upper()
        if not ticker or ticker == "NAN":
            continue
        quantity = _row_number(row, quantity_cols) or 0.0
        position = PortfolioPosition(
            ticker=ticker,
            quantity=quantity,
            average_price=_row_number(row, avg_cols),
            last_price=_row_number(row, last_cols),
            invested_value=_row_number(row, invested_cols),
            current_value=_row_number(row, current_cols),
            pnl=_row_number(row, pnl_cols),
            pnl_pct=_row_number(row, pnl_pct_cols),
            broker=provider,
            asset_class=_row_text(row, asset_cols, "equity"),
        )
        if position.value() <= 0:
            warnings.append(f"row {row_number + 2}: {ticker} has no usable position value")
            continue
        positions.append(position)
    if not positions:
        raise ValueError("portfolio spreadsheet contains no usable positions")
    currency = _row_text(frame.iloc[0], currency_cols, "INR").upper()
    return PortfolioSnapshot(provider=provider, positions=positions, currency=currency, source="spreadsheet", warnings=warnings)


def load_portfolio_file(path: str | Path, provider: str = "excel") -> PortfolioSnapshot:
    file_path = Path(path)
    if not file_path.exists():
        raise ValueError(f"portfolio file not found: {file_path}")
    suffix = file_path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(file_path)
    elif suffix == ".csv":
        frame = pd.read_csv(file_path)
    else:
        raise ValueError("portfolio upload must be .xlsx, .xls or .csv")
    return positions_from_dataframe(frame, provider=provider)


def load_portfolio_bytes(filename: str, content: bytes, provider: str = "excel") -> PortfolioSnapshot:
    suffix = Path(filename).suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(BytesIO(content))
    elif suffix == ".csv":
        frame = pd.read_csv(BytesIO(content))
    else:
        raise ValueError("portfolio upload must be .xlsx, .xls or .csv")
    return positions_from_dataframe(frame, provider=provider)


class ZerodhaPortfolioPlugin:
    name = "zerodha"

    def __init__(self, api_key: str | None = None, access_token: str | None = None) -> None:
        self.api_key = api_key or os.getenv("ZERODHA_API_KEY")
        self.access_token = access_token or os.getenv("ZERODHA_ACCESS_TOKEN")

    def holdings(self) -> PortfolioSnapshot:
        if not self.api_key or not self.access_token:
            raise ValueError("ZERODHA_API_KEY and ZERODHA_ACCESS_TOKEN are required")
        response = httpx.get(
            "https://api.kite.trade/portfolio/holdings",
            headers={
                "X-Kite-Version": "3",
                "Authorization": f"token {self.api_key}:{self.access_token}",
            },
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "success":
            raise ValueError(str(payload.get("message") or "Zerodha holdings request failed"))
        positions: list[PortfolioPosition] = []
        for item in payload.get("data", []):
            quantity = float(item.get("quantity") or 0) + float(item.get("t1_quantity") or 0)
            mtf = item.get("mtf") or {}
            quantity += float(mtf.get("quantity") or 0)
            last_price = _number(item.get("last_price"))
            average_price = _number(item.get("average_price"))
            positions.append(PortfolioPosition(
                ticker=str(item.get("tradingsymbol") or item.get("exchange_token") or "").upper(),
                quantity=quantity,
                average_price=average_price,
                last_price=last_price,
                invested_value=average_price * quantity if average_price is not None else None,
                current_value=last_price * quantity if last_price is not None else None,
                pnl=_number(item.get("pnl")),
                pnl_pct=None,
                broker="zerodha",
                asset_class="equity",
            ))
        positions = [item for item in positions if item.ticker and item.value() > 0]
        if not positions:
            raise ValueError("Zerodha returned no usable holdings")
        return PortfolioSnapshot(provider="zerodha", positions=positions, currency="INR", source="kite", warnings=[])


class INDMoneyPortfolioPlugin:
    name = "indmoney"

    def import_statement(self, path: str | Path) -> PortfolioSnapshot:
        return load_portfolio_file(path, provider="indmoney")

    def import_bytes(self, filename: str, content: bytes) -> PortfolioSnapshot:
        return load_portfolio_bytes(filename, content, provider="indmoney")


def portfolio_plugin(name: str, **kwargs: Any) -> Any:
    key = name.strip().lower()
    if key == "zerodha":
        return ZerodhaPortfolioPlugin(**kwargs)
    if key == "indmoney":
        return INDMoneyPortfolioPlugin()
    raise ValueError("portfolio plugin must be zerodha or indmoney")
