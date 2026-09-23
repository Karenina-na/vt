"""Evaluate a strategy across symbols and catalog time windows."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import pandas as pd

from ntquant.backtest.instruments import make_bar_type
from ntquant.backtest.runner import run_backtest
from ntquant.config import BacktestConfig
from ntquant.data.catalog import DataCatalog
from ntquant.research.metrics import extract_six
from ntquant.research.symbols import SymbolSpec, get_spec
from ntquant.strategies.registry import canonical


@dataclass
class EvaluationResult:
    """Aggregated evaluation table + per-run details."""

    frame: pd.DataFrame

    def to_csv(self, path: str) -> str:
        self.frame.to_csv(path, index=False)
        return path


def _symbol_config(
    base: BacktestConfig,
    spec: SymbolSpec,
    market: str,
    factor: str,
) -> BacktestConfig:
    """Derive a single-symbol BacktestConfig from the base config."""
    from ntquant.config import DataConfig, InstrumentConfig, VenueConfig

    instrument_id = spec.instrument_id(market)
    bar_type = spec.bar_type(market)
    size_precision = spec.size_precision(market)

    instrument = InstrumentConfig(
        asset_class="CRYPTOCURRENCY",
        instrument_id=instrument_id,
        raw_symbol=(
            f"{spec.symbol}USDT-PERP" if market == "perp" else f"{spec.symbol}USDT"
        ),
        base_currency=str(spec.base_currency),
        quote_currency="USDT",
        settlement_currency="USDT",
        price_precision=spec.price_precision,
        size_precision=size_precision,
        price_increment=f"{1 / 10 ** spec.price_precision:.{spec.price_precision}f}",
        size_increment=f"{1 / 10 ** size_precision:.{size_precision}f}",
        min_quantity=f"{1 / 10 ** size_precision:.{size_precision}f}",
        start_price=spec.start_price,
    )

    data = DataConfig(
        instrument_id=instrument_id,
        catalog_path=base.data.catalog_path,
        bar_type=bar_type,
        source="binance",
        tz="UTC",
        proxy=base.data.proxy,
    )

    strategy = replace(
        base.strategy,
        strategy_id=f"{canonical(factor)}-{spec.symbol}",
        bar_type=bar_type,
    )

    # Venue must match the instrument's venue (BINANCE for perp, BINANCESPOT for
    # spot) and the account currency is USDT.
    venue = VenueConfig(
        name=spec.venue_name(market),
        oms_type=base.venue.oms_type,
        account_type=base.venue.account_type,
        base_currency="USDT",
        starting_balance=base.venue.starting_balance,
        default_leverage=base.venue.default_leverage,
    )

    return BacktestConfig(
        venue=venue,
        instrument=instrument,
        strategy=strategy,
        data=data,
        output_path=base.output_path,
        log_level=base.log_level,
    )


def _to_ns(value: str | None) -> int | None:
    if value is None:
        return None
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return int(ts.value)


def _load_window_bars(
    config: BacktestConfig, start: str | None, end: str | None
) -> list:
    """Load catalog bars for the config's bar_type, sliced to [start, end]."""
    catalog = DataCatalog(config.data.catalog_path)
    bar_type = make_bar_type(config.data.bar_type)
    return catalog.load_bars(
        config.data.instrument_id,
        bar_type,
        start=_to_ns(start),
        end=_to_ns(end),
    )


def evaluate_factor(
    factor: str,
    symbol: str,
    base: BacktestConfig,
    market: str = "perp",
    start: str | None = None,
    end: str | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one backtest for factor x symbol and return six metrics + identifiers."""
    spec = get_spec(symbol)
    config = _symbol_config(base, spec, market, factor)
    bars = _load_window_bars(config, start, end)
    if not bars:
        raise ValueError(
            f"No catalog bars for {config.data.instrument_id} / {config.data.bar_type}"
        )
    outcome = run_backtest(
        config, bars=bars, strategy_name=factor, strategy_params=params
    )

    metrics = extract_six(outcome)
    row = {
        "factor": factor,
        "symbol": spec.symbol,
        "market": market,
        **metrics,
    }
    outcome.engine.dispose()
    return row


def run_factor_evaluation(
    factor: str,
    symbols: list[str],
    base: BacktestConfig,
    market: str = "perp",
    start: str | None = None,
    end: str | None = None,
    params: dict[str, Any] | None = None,
) -> EvaluationResult:
    """Evaluate a factor across symbols; returns a stacked comparison table.

    Serial execution keeps memory low. Symbols with no bars in the window are
    dropped (an empty backtest has no metrics to report).
    """
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        try:
            row = evaluate_factor(
                factor, symbol, base, market=market, start=start, end=end, params=params
            )
            if row["pnl"] is not None or row["pnl_pct"] is not None:
                rows.append(row)
        except Exception as exc:  # noqa: BLE001 - skip a bad symbol, keep going
            rows.append(
                {
                    "factor": factor,
                    "symbol": symbol,
                    "market": market,
                    "pnl": None,
                    "pnl_pct": None,
                    "win_rate": None,
                    "profit_factor": None,
                    "sharpe": None,
                    "max_drawdown": None,
                    "error": str(exc),
                }
            )
    return EvaluationResult(frame=pd.DataFrame(rows))
