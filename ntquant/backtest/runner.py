"""Backtest runner using the low-level ``BacktestEngine`` (1.231.0).

Notes (verified against 1.231.0):
- ``BacktestEngine`` lives in ``nautilus_trader.backtest.engine``.
- ``strategy_id`` must be a plain ``str`` to avoid a ``name`` type error in the
  Rust ``Strategy`` base class.
- ``make_qty`` normalises order quantity to the instrument's ``size_precision``.
- Reports come from ``ReportProvider`` (the engine has no ``generate_*`` report
  methods in this version); ``engine.get_result()`` provides performance stats.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from nautilus_trader.analysis import ReportProvider
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import BacktestEngineConfig, LoggingConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.identifiers import InstrumentId, Venue
from nautilus_trader.model.objects import Money

from ntquant.backtest.instruments import make_bar_type, make_instrument
from ntquant.config import BacktestConfig
from ntquant.strategies.ema_cross import EMACrossConfig, EMACrossStrategy

# Strategy registry: ``config.strategy.name`` -> factory(config, strategy_cfg).
# Add new strategies here and to the ``STRATEGY_CONFIGS`` map when needed.
STRATEGY_CONFIGS = {
    "ema_cross": EMACrossConfig,
}


@dataclass
class BacktestOutcome:
    """Collected results from a completed backtest run."""

    config: BacktestConfig
    engine: BacktestEngine
    orders_df: object
    fills_df: object
    positions_df: object
    account_df: object
    stats: object

    def save(self, output_dir: str, prefix: str = "run") -> dict[str, str]:
        """Persist reports to CSV and return the written file paths."""
        from pathlib import Path

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        paths: dict[str, str] = {}
        for name, df in {
            "orders": self.orders_df,
            "fills": self.fills_df,
            "positions": self.positions_df,
            "account": self.account_df,
        }.items():
            if df is not None and getattr(df, "shape", (0,))[0] > 0:
                path = out / f"{prefix}_{name}.csv"
                df.to_csv(path)
                paths[name] = str(path)
        return paths


def build_engine(config: BacktestConfig, risk_engine=None) -> BacktestEngine:
    """Create a configured low-level backtest engine.

    Args:
        config: Backtest configuration.
        risk_engine: Optional ``RiskEngineConfig`` wired into the engine.

    Note: passing ``risk_engine=None`` explicitly triggers a kernel bug in
    1.231.0 (``NautilusKernel has no attribute '_risk_engine'``), so the
    keyword is omitted entirely when unset.
    """
    kwargs = dict(logging=LoggingConfig(log_level=config.log_level))
    if risk_engine is not None:
        kwargs["risk_engine"] = risk_engine
    return BacktestEngine(config=BacktestEngineConfig(**kwargs))


def make_strategy(config: BacktestConfig):
    """Build a strategy instance from the configured strategy name.

    The strategy config class is looked up in ``STRATEGY_CONFIGS``; its extra
    fields are assembled from ``config.strategy`` (the frozen dataclass) so new
    strategies can add their own parameters to ``StrategyConfig``.
    """
    name = config.strategy.name
    cfg_cls = STRATEGY_CONFIGS.get(name)
    if cfg_cls is None:
        raise ValueError(f"Unknown strategy '{name}'. Registered: {list(STRATEGY_CONFIGS)}")

    cfg = cfg_cls(
        instrument_id=InstrumentId.from_str(config.instrument.instrument_id),
        bar_type=make_bar_type(config.strategy.bar_type),
        trade_size=config.strategy.trade_size,
        fast_period=config.strategy.fast_period,
        slow_period=config.strategy.slow_period,
        strategy_id=config.strategy.strategy_id,
    )
    if name == "ema_cross":
        return EMACrossStrategy(cfg)
    # When adding a strategy, map cfg_cls -> its Strategy subclass here.
    raise NotImplementedError(f"Strategy '{name}' config exists but has no builder")


def run_backtest(config: BacktestConfig, use_catalog: bool = False) -> BacktestOutcome:
    """Run a single backtest and collect outcome + reports.

    Args:
        config: Backtest configuration.
        use_catalog: If True, load bars from the data catalog first
            (``docs/data``); otherwise generate synthetic bars in memory.

    Returns:
        A :class:`BacktestOutcome` holding reports and engine statistics.
    """
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

    bars = _load_bars(config, bar_type, use_catalog)
    engine.add_data(bars)

    engine.add_strategy(make_strategy(config))
    engine.run()

    orders = engine.cache.orders()
    positions = engine.cache.positions()
    snapshots = engine.cache.position_snapshots()

    accounts = list(engine.cache.accounts())
    account = accounts[0] if accounts else None

    outcome = BacktestOutcome(
        config=config,
        engine=engine,
        orders_df=ReportProvider.generate_orders_report(orders),
        fills_df=ReportProvider.generate_order_fills_report(orders),
        positions_df=ReportProvider.generate_positions_report(positions, snapshots),
        account_df=ReportProvider.generate_account_report(account) if account else None,
        stats=engine.get_result(),
    )
    return outcome


def _account_type(name: str) -> AccountType:
    """Resolve an account type name to an ``AccountType`` enum member.

    ``AccountType`` members carry integer values (CASH=1, MARGIN=2, ...), so
    ``AccountType("MARGIN")``/``AccountType("margin")`` raises. Match by member
    name instead, defaulting to MARGIN.
    """
    n = name.upper()
    if hasattr(AccountType, n):
        return getattr(AccountType, n)
    return AccountType.MARGIN


def _currency(code: str):
    """Resolve a currency code to a Nautilus ``Currency`` (falls back to USD)."""
    from nautilus_trader.model.objects import Currency

    if not code:
        return USD
    try:
        return Currency.from_str(code)
    except Exception:
        return USD


def _load_bars(config: BacktestConfig, bar_type, use_catalog: bool) -> list:
    """Load bars either from the catalog or from synthetic generation.

    When ``config.data.source`` is set to a real source (anything other than
    ``"synthetic"``), we assume the data has already been ingested into the
    catalog and read it from there regardless of ``use_catalog``.
    """
    source = config.data.source or "synthetic"
    real_source = source.lower() != "synthetic"

    if use_catalog or real_source:
        from ntquant.data.catalog import DataCatalog

        catalog = DataCatalog(config.data.catalog_path)
        instrument_id = config.data.instrument_id
        bars = catalog.load_bars(instrument_id, bar_type)
        if bars:
            return bars
        if real_source:
            raise ValueError(
                f"Catalog has no bars for {instrument_id} / {bar_type}. "
                f"Run `ntquant ingest --source {source}` (or `make ingest`) first."
            )
    from ntquant.data.synthetic import generate_synthetic_bars

    inst = config.instrument
    return generate_synthetic_bars(
        bar_type,
        count=config.data.count,
        seed=config.data.seed,
        start_price=inst.start_price,
        price_precision=inst.price_precision,
        volume_precision=inst.size_precision,
    )
