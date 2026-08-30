"""Research evaluation runner: factor x symbol x time-window.

This module is intentionally standalone: it does not modify the core backtest
scaffold. For each symbol it builds a per-symbol config, loads catalog bars
sliced to ``[start, end]`` directly, constructs a low-level ``BacktestEngine``
(reusing the scaffold's public helpers), and extracts the fixed six metrics.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pandas as pd

from nautilus_trader.analysis import ReportProvider
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.objects import Money

from ntquant.backtest.instruments import make_bar_type, make_instrument
from ntquant.backtest.runner import BacktestOutcome, build_engine
from ntquant.config import BacktestConfig
from ntquant.data.catalog import DataCatalog
from ntquant.research.factors import build_factor
from ntquant.research.metrics import extract_six
from ntquant.research.symbols import SymbolSpec, get_spec


@dataclass
class EvaluationResult:
    """Aggregated evaluation table + per-run details."""

    frame: pd.DataFrame

    def to_csv(self, path: str) -> str:
        self.frame.to_csv(path, index=False)
        return path


def _account_type(name: str) -> AccountType:
    n = name.upper()
    return getattr(AccountType, n, AccountType.MARGIN)


def _currency(code: str):
    from nautilus_trader.model.objects import Currency

    if not code:
        from nautilus_trader.model.currencies import USDT

        return USDT
    try:
        return Currency.from_str(code)
    except Exception:  # noqa: BLE001 - fall back to USDT
        from nautilus_trader.model.currencies import USDT

        return USDT


def _symbol_config(
    base: BacktestConfig,
    spec: SymbolSpec,
    market: str,
) -> BacktestConfig:
    """Derive a single-symbol BacktestConfig from the base config."""
    from ntquant.config import DataConfig, InstrumentConfig, StrategyConfig, VenueConfig

    instrument_id = spec.instrument_id(market)
    bar_type = spec.bar_type(market)
    size_precision = spec.size_precision(market)

    instrument = InstrumentConfig(
        asset_class="CRYPTOCURRENCY",
        instrument_id=instrument_id,
        raw_symbol=f"{spec.symbol}USDT-PERP" if market == "perp" else f"{spec.symbol}USDT",
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

    strategy = StrategyConfig(
        name=base.strategy.name,
        strategy_id=f"{base.strategy.name}-{spec.symbol}",
        trade_size=base.strategy.trade_size,
        fast_period=base.strategy.fast_period,
        slow_period=base.strategy.slow_period,
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


def _load_window_bars(config: BacktestConfig, start: str | None, end: str | None) -> list:
    """Load catalog bars for the config's bar_type, sliced to [start, end]."""
    catalog = DataCatalog(config.data.catalog_path)
    bar_type = make_bar_type(config.data.bar_type)
    return catalog.load_bars(
        config.data.instrument_id,
        bar_type,
        start=_to_ns(start),
        end=_to_ns(end),
    )


def _run_window(
    config: BacktestConfig,
    factor: str,
    start: str | None,
    end: str | None,
    params: dict[str, Any] | None = None,
) -> BacktestOutcome:
    """Build an engine, feed sliced catalog bars, run, and collect the outcome."""
    venue_name = config.venue.name
    bar_type = make_bar_type(config.strategy.bar_type)
    instrument = make_instrument(config)

    account_type = _account_type(config.venue.account_type)
    base_currency = _currency(config.venue.base_currency)

    engine = build_engine(config)
    engine.add_venue(
        venue=Venue(venue_name),
        oms_type=OmsType.NETTING,
        account_type=account_type,
        base_currency=base_currency,
        starting_balances=[Money(Decimal(str(config.venue.starting_balance)), base_currency)],
        default_leverage=Decimal(config.venue.default_leverage),
    )
    engine.add_instrument(instrument)

    bars = _load_window_bars(config, start, end)
    if not bars:
        raise ValueError(f"No catalog bars for {config.data.instrument_id} / {config.data.bar_type}")
    engine.add_data(bars)

    strategy = build_factor(factor, config, params)
    engine.add_strategy(strategy)
    engine.run()

    orders = engine.cache.orders()
    positions = engine.cache.positions()
    snapshots = engine.cache.position_snapshots()
    accounts = list(engine.cache.accounts())
    account = accounts[0] if accounts else None

    return BacktestOutcome(
        config=config,
        engine=engine,
        orders_df=ReportProvider.generate_orders_report(orders),
        fills_df=ReportProvider.generate_order_fills_report(orders),
        positions_df=ReportProvider.generate_positions_report(positions, snapshots),
        account_df=ReportProvider.generate_account_report(account) if account else None,
        stats=engine.get_result(),
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
    config = _symbol_config(base, spec, market)
    outcome = _run_window(config, factor, start, end, params)

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
