"""Fixed six-metric evaluation for a backtest outcome.

The six metrics (chosen for research comparison) are:
- ``pnl``        : total PnL in account quote currency
- ``pnl_pct``    : total PnL as % of starting balance
- ``win_rate``   : fraction of winning trades
- ``profit_factor`` : gross profit / gross loss
- ``sharpe``     : annualised Sharpe ratio (252 days)
- ``max_drawdown`` : maximum peak-to-trough equity decline (%)

``max_drawdown`` is computed from the account equity curve (``account_df``)
because nautilus ``stats_returns`` does not expose it directly.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from ntquant.backtest.runner import BacktestOutcome

METRIC_KEYS = (
    "pnl",
    "pnl_pct",
    "win_rate",
    "profit_factor",
    "sharpe",
    "max_drawdown",
)


def compute_max_drawdown(account_df) -> float | None:
    """Return the max peak-to-trough equity drawdown as a positive %."""
    if account_df is None or getattr(account_df, "shape", (0,))[0] == 0:
        return None
    equity = account_df["total"].astype(float)
    running_max = equity.cummax()
    drawdowns = (equity - running_max) / running_max
    return -round(float(drawdowns.min()) * 100, 4) if len(drawdowns) else None


def extract_six(outcome: BacktestOutcome) -> dict[str, Any]:
    """Extract the fixed six metrics from a backtest outcome."""
    stats = outcome.stats
    pnls = getattr(stats, "stats_pnls", {}) or {}
    returns = getattr(stats, "stats_returns", {}) or {}
    # Use the first currency bucket (USDT in all our crypto/spot setups).
    usd = pnls.get("USDT") or (next(iter(pnls.values())) if pnls else {})
    usd = usd or {}

    return {
        "pnl": usd.get("PnL (total)"),
        "pnl_pct": usd.get("PnL% (total)"),
        "win_rate": usd.get("Win Rate"),
        "profit_factor": returns.get("Profit Factor"),
        "sharpe": returns.get("Sharpe Ratio (252 days)"),
        "max_drawdown": compute_max_drawdown(
            getattr(outcome, "account_df", None)
        ),
    }


def metrics_frame(outcome: BacktestOutcome) -> pd.DataFrame:
    """Return the six metrics as a single-row DataFrame."""
    return pd.DataFrame([extract_six(outcome)])


__all__ = ["METRIC_KEYS", "compute_max_drawdown", "extract_six", "metrics_frame"]
