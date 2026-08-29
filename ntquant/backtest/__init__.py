"""Backtest layer: low/high-level runners and parameter scanning."""
from ntquant.backtest.parameters import scan_parameters
from ntquant.backtest.runner import BacktestOutcome, run_backtest

__all__ = ["BacktestOutcome", "run_backtest", "scan_parameters"]
