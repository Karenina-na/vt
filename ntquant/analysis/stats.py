"""Performance statistics from a backtest outcome."""
from __future__ import annotations

import pandas as pd

from ntquant.backtest.runner import BacktestOutcome


def performance_summary(outcome: BacktestOutcome) -> dict[str, float | int | None]:
    """Extract a flat performance summary dict from a backtest result."""
    stats = outcome.stats
    pnls = getattr(stats, "stats_pnls", {}) or {}
    returns = getattr(stats, "stats_returns", {}) or {}
    usd = pnls.get("USD", {}) or {}
    return {
        "total_positions": len(outcome.engine.cache.positions_closed()),
        "pnl_total": usd.get("PnL (total)"),
        "pnl_pct": usd.get("PnL% (total)"),
        "win_rate": usd.get("Win Rate"),
        "expectancy": usd.get("Expectancy"),
        "avg_winner": usd.get("Avg Winner"),
        "avg_loser": usd.get("Avg Loser"),
        "sharpe_ratio": returns.get("Sharpe Ratio (252 days)"),
        "sortino_ratio": returns.get("Sortino Ratio (252 days)"),
        "profit_factor": returns.get("Profit Factor"),
        "max_drawdown": returns.get("Max Drawdown"),
    }


def summary_frame(outcome: BacktestOutcome) -> pd.DataFrame:
    """Return the performance summary as a single-column DataFrame."""
    return pd.DataFrame([performance_summary(outcome)]).T
