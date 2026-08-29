"""Visualization: interactive HTML tearsheet."""
from __future__ import annotations

from pathlib import Path

from nautilus_trader.analysis import create_tearsheet


def make_tearsheet(
    outcome,
    output_path: str = "output/tearsheet.html",
    title: str = "NautilusTrader Backtest Results",
) -> str:
    """Generate an interactive Plotly HTML tearsheet and return its path."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    create_tearsheet(outcome.engine, output_path=output_path, title=title)
    return output_path
