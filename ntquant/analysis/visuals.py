"""Interactive HTML performance and trade charts."""
from __future__ import annotations

from pathlib import Path

from nautilus_trader.analysis import create_tearsheet
from nautilus_trader.analysis.tearsheet import create_bars_with_fills

from ntquant.backtest.instruments import make_bar_type


def make_tearsheet(
    outcome,
    output_path: str = "output/tearsheet.html",
    title: str = "NautilusTrader Backtest Results",
) -> str:
    """Generate an interactive Plotly HTML tearsheet and return its path."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    create_tearsheet(outcome.engine, output_path=output_path, title=title)
    return output_path


def make_trade_chart(outcome, output_path: str | Path) -> str:
    """Export interactive price bars with buy and sell fills."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    create_bars_with_fills(
        outcome.engine,
        make_bar_type(outcome.config.strategy.bar_type),
        output_path=str(path),
    )
    return str(path)
