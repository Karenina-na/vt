"""Grid scanning for the configured strategy."""
from __future__ import annotations

from dataclasses import replace
from itertools import product
from typing import Any

import pandas as pd

from ntquant.backtest.runner import BacktestOutcome, run_backtest
from ntquant.config import BacktestConfig, ParamScanConfig


def _build_config(base: BacktestConfig, params: dict[str, Any]) -> BacktestConfig:
    """Return a backtest config with one parameter combination applied."""
    specific = {key: value for key, value in params.items() if key != "trade_size"}
    strategy = replace(
        base.strategy,
        trade_size=str(params.get("trade_size", base.strategy.trade_size)),
        params={**base.strategy.params, **specific},
    )
    return replace(base, strategy=strategy)


def _grid(scandef: dict[str, list[Any]]) -> list[dict[str, Any]]:
    keys = list(scandef.keys())
    vals = [scandef[k] if isinstance(scandef[k], list) else [scandef[k]] for k in keys]
    return [dict(zip(keys, combo)) for combo in product(*vals)]


def _summary(outcome: BacktestOutcome) -> dict[str, Any]:
    stats = outcome.stats
    pnls = getattr(stats, "stats_pnls", {}) or {}
    returns = getattr(stats, "stats_returns", {}) or {}
    usd = pnls.get("USD", {}) or {}
    return {
        "total_positions": len(outcome.engine.cache.positions_closed()),
        "pnl_total": usd.get("PnL (total)"),
        "win_rate": usd.get("Win Rate"),
        "expectancy": usd.get("Expectancy"),
        "sharpe_ratio": returns.get("Sharpe Ratio (252 days)"),
        "profit_factor": returns.get("Profit Factor"),
    }


def scan_parameters(
    base_config: BacktestConfig,
    param_config: ParamScanConfig,
) -> pd.DataFrame:
    """Run a grid search over strategy parameters and return a results table."""
    base_config = replace(
        base_config,
        data=param_config.data,
        log_level=param_config.log_level,
    )
    rows: list[dict[str, Any]] = []
    for params in _grid(param_config.scan):
        cfg = _build_config(base_config, params)
        outcome = run_backtest(cfg)
        row = _summary(outcome)
        row.update({f"param_{k}": v for k, v in params.items()})
        rows.append(row)
        outcome.engine.dispose()

    return pd.DataFrame(rows)
