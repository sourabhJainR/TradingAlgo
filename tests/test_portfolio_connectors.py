from __future__ import annotations

import pandas as pd
import pytest

from tradingalgo.intelligence.portfolio_connectors import (
    INDMoneyPortfolioPlugin,
    PortfolioPosition,
    PortfolioSnapshot,
    load_portfolio_bytes,
    positions_from_dataframe,
)


def test_excel_positions_normalize_common_columns() -> None:
    frame = pd.DataFrame(
        [
            {"Symbol": "NVDA", "Qty": 10, "Avg Price": 100, "LTP": 150},
            {"Symbol": "MSFT", "Quantity": 5, "Average Price": 200, "Current Value": 1200},
        ]
    )
    snapshot = positions_from_dataframe(frame)
    assert snapshot.provider == "excel"
    assert [item.ticker for item in snapshot.positions] == ["NVDA", "MSFT"]
    assert snapshot.weights()["NVDA"] > 50


def test_indmoney_plugin_reads_excel_bytes() -> None:
    frame = pd.DataFrame(
        [{"Security Name": "RELIANCE", "Quantity": 10, "Average Price": 2000, "Current Value": 25000}]
    )
    import io

    buffer = io.BytesIO()
    frame.to_excel(buffer, index=False)
    snapshot = INDMoneyPortfolioPlugin().import_bytes("portfolio.xlsx", buffer.getvalue())
    assert snapshot.provider == "indmoney"
    assert snapshot.positions[0].ticker == "RELIANCE"
    assert snapshot.positions[0].current_value == 25000


def test_snapshot_requires_positive_value() -> None:
    snapshot = PortfolioSnapshot(
        provider="test",
        positions=[PortfolioPosition("AAA", 0, average_price=0)],
    )
    with pytest.raises(ValueError, match="no positions"):
        snapshot.weights()


def test_unsupported_upload_type_rejected() -> None:
    with pytest.raises(ValueError, match="xlsx, .xls or .csv"):
        load_portfolio_bytes("portfolio.pdf", b"data")
