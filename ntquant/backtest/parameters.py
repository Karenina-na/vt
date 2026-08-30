"""Parameter scanning for the EMA cross strategy (zero-dependency grid)."""
from __future__ import annotations

from itertools import product
from typing import Any

import pandas as pd

from ntquant.backtest.runner import BacktestOutcome, run_backtest
from ntquant.config import BacktestConfig, ParamScanConfig


def _build_config(base: BacktestConfig, params: dict[str, Any]) -> BacktestConfig:
    """Return a new BacktestConfig overriding strategy parameters.

    The ``data`` section is preserved in full (source/tz/columns/timestamp_col are
    carried through) so a real-data scan still resolves the catalog.
    """
    s = base.strategy
    new_strategy = type(s)(
        name=s.name,
        strategy_id=s.strategy_id,
        trade_size=str(params.get("trade_size", s.trade_size)),
        fast_period=int(params.get("fast_period", s.fast_period)),
        slow_period=int(params.get("slow_period", s.slow_period)),
        bar_type=s.bar_type,
    )
    d = base.data
    new_data = type(d)(
        instrument_id=d.instrument_id,
        count=d.count,
        seed=d.seed,
        catalog_path=d.catalog_path,
        bar_type=d.bar_type,
        source=d.source,
        source_path=d.source_path,
        tz=d.tz,
        columns=d.columns,
        timestamp_col=d.timestamp_col,
        proxy=d.proxy,
    )
    return BacktestConfig(
        venue=base.venue,
        instrument=base.instrument,
        strategy=new_strategy,
        data=new_data,
        output_path=base.output_path,
        log_level=base.log_level,
    )


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
    rows: list[dict[str, Any]] = []
    for params in _grid(param_config.scan):
        cfg = _build_config(base_config, params)
        outcome = run_backtest(cfg)
        row = _summary(outcome)
        row.update({f"param_{k}": v for k, v in params.items()})
        rows.append(row)
        outcome.engine.dispose()

    return pd.DataFrame(rows)
