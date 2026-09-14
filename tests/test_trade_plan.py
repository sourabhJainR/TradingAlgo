from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tradingalgo.intelligence.trade_plan import build_trade_plan


def test_build_trade_plan_produces_ordered_levels() -> None:
    close = np.linspace(100.0, 150.0, 80)
    frame = pd.DataFrame({
        "open": close - 1,
        "high": close + 2,
        "low": close - 2,
        "close": close,
        "volume": np.full(80, 100_000),
    })
    plan = build_trade_plan("ABC", frame)
    assert plan.buy_range_low <= plan.buy_range_high <= plan.target_1 <= plan.target_2
    assert plan.stop_loss < plan.buy_range_low
    assert plan.risk_reward_t1 == 1.0
    assert plan.risk_reward_t2 == 2.0
    assert plan.prediction_basis


def test_build_trade_plan_requires_history() -> None:
    frame = pd.DataFrame({"open": [1] * 20, "high": [2] * 20, "low": [0.5] * 20, "close": [1.5] * 20, "volume": [100] * 20})
    with pytest.raises(ValueError, match="50"):
        build_trade_plan("ABC", frame)
