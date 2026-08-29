"""Report generation from a completed backtest outcome."""
from __future__ import annotations

from ntquant.backtest.runner import BacktestOutcome


def generate_all_reports(outcome: BacktestOutcome, output_dir: str, prefix: str = "run") -> dict[str, str]:
    """Save all report DataFrames to CSV and return the written paths."""
    return outcome.save(output_dir, prefix=prefix)
