"""Strategy (factor) registry for research evaluation.

A "factor" is a standard Nautilus ``Strategy`` subclass (registered here together
with its ``StrategyConfig``). Adding a new factor means subclassing
``BaseStrategy``/``BaseStrategyConfig`` and registering it in both
``FACTORY_CONFIGS`` and ``FACTOR_BUILDERS``.

``build_factor`` instantiates a factor from a base strategy config by copying
the fields the factor's ``StrategyConfig`` declares (reflectively), so a new
factor only needs to be registered here — the research runner does not modify
the core scaffold's ``make_strategy``.
"""
from __future__ import annotations

import dataclasses
from typing import Any

from ntquant.strategies.base import BaseStrategy, BaseStrategyConfig
from ntquant.strategies.bollinger_reversal import (
    BollingerReversalConfig,
    BollingerReversalStrategy,
)
from ntquant.strategies.ema_cross import EMACrossConfig, EMACrossStrategy
from ntquant.strategies.macd_cross import MacdCrossConfig, MacdCrossStrategy
from ntquant.strategies.roc_momentum import RocMomentumConfig, RocMomentumStrategy
from ntquant.strategies.rsi_reversal import RsiReversalConfig, RsiReversalStrategy

# Factor name -> StrategyConfig class (declares the factor's tunable fields).
FACTORY_CONFIGS: dict[str, type[BaseStrategyConfig]] = {
    "ema_cross": EMACrossConfig,
    "rsi_reversal": RsiReversalConfig,
    "bollinger_reversal": BollingerReversalConfig,
    "roc_momentum": RocMomentumConfig,
    "macd_cross": MacdCrossConfig,
}

# Factor name -> Strategy class.
FACTOR_BUILDERS: dict[str, type[BaseStrategy]] = {
    "ema_cross": EMACrossStrategy,
    "rsi_reversal": RsiReversalStrategy,
    "bollinger_reversal": BollingerReversalStrategy,
    "roc_momentum": RocMomentumStrategy,
    "macd_cross": MacdCrossStrategy,
}

# Default factor params, used when the base strategy config lacks a matching field.
DEFAULT_PARAMS: dict[str, dict[str, Any]] = {
    "ema_cross": {},
    "rsi_reversal": {"period": 14, "oversold": 30.0, "overbought": 70.0},
    "bollinger_reversal": {"period": 20, "num_std": 2.0},
    "roc_momentum": {"period": 10, "entry_threshold": 1.0},
    "macd_cross": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
}

# Aliases for convenience (snake_case variants).
ALIASES = {
    "ema": "ema_cross",
    "emacross": "ema_cross",
    "rsi": "rsi_reversal",
    "bollinger": "bollinger_reversal",
    "bb": "bollinger_reversal",
    "roc": "roc_momentum",
    "macd": "macd_cross",
}

SUPPORTED_FACTORS = tuple(
    sorted(set(FACTORY_CONFIGS) | set(FACTOR_BUILDERS) | set(ALIASES))
)


def canonical(name: str) -> str:
    """Resolve a factor name (or alias) to its canonical key."""
    key = name.lower()
    return ALIASES.get(key, key)


def _field_names(cls_or_inst) -> set[str]:
    """Return declared field names for a dataclass or msgspec Struct."""
    if hasattr(cls_or_inst, "__struct_fields__"):
        return set(getattr(cls_or_inst, "__struct_fields__"))
    if dataclasses.is_dataclass(cls_or_inst):
        return {f.name for f in dataclasses.fields(cls_or_inst)}
    return set()


def build_factor(factor: str, config, params: dict[str, Any] | None = None) -> BaseStrategy:
    """Instantiate a factor's strategy from a backtest config.

    Args:
        factor: Canonical factor name (see ``canonical``).
        config: The full ``BacktestConfig``; its ``strategy`` (a scaffold
            dataclass) carries shared fields and ``instrument`` the instrument_id.
        params: Optional overrides for the factor's own tunable fields.

    The factor's ``StrategyConfig`` is built by copying the shared fields from
    ``config.strategy`` and filling the declared factor fields with ``params``
    (or the registered defaults). This keeps new factors zero-boilerplate and
    does not touch the scaffold's ``make_strategy``.
    """
    from ntquant.backtest.instruments import make_bar_type
    from nautilus_trader.model.identifiers import InstrumentId

    key = canonical(factor)
    cfg_cls = FACTORY_CONFIGS.get(key)
    builder = FACTOR_BUILDERS.get(key)
    if cfg_cls is None or builder is None:
        raise ValueError(
            f"Unknown factor '{factor}'. Registered: {sorted(FACTOR_BUILDERS)}"
        )

    base_cfg = config.strategy
    declared = _field_names(cfg_cls)
    overrides = dict(DEFAULT_PARAMS.get(key, {}))
    if params:
        overrides.update(params)

    # Shared fields come from the base (scaffold dataclass) strategy config.
    kwargs: dict[str, Any] = {}
    for field in dataclasses.fields(base_cfg):
        if field.name in declared:
            kwargs[field.name] = getattr(base_cfg, field.name)

    # Guarantee the required identifiers are present.
    if "instrument_id" in declared:
        kwargs["instrument_id"] = InstrumentId.from_str(config.instrument.instrument_id)
    if "bar_type" in declared:
        kwargs["bar_type"] = make_bar_type(base_cfg.bar_type)
    if "trade_size" not in kwargs:
        kwargs["trade_size"] = base_cfg.trade_size
    if "strategy_id" not in kwargs:
        kwargs["strategy_id"] = base_cfg.strategy_id

    # Factor-specific (or default) params.
    for k, v in overrides.items():
        if k in declared:
            kwargs[k] = v

    cfg = cfg_cls(**kwargs)
    return builder(cfg)
