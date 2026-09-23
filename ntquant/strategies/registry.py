"""Strategy registration and configuration shared by backtests and research."""
from __future__ import annotations

from typing import Any

from nautilus_trader.model.identifiers import InstrumentId

from ntquant.backtest.instruments import make_bar_type
from ntquant.config import BacktestConfig
from ntquant.strategies.base import BaseStrategy, BaseStrategyConfig
from ntquant.strategies.bollinger_reversal import (
    BollingerReversalConfig,
    BollingerReversalStrategy,
)
from ntquant.strategies.ema_cross import EMACrossConfig, EMACrossStrategy
from ntquant.strategies.macd_cross import MacdCrossConfig, MacdCrossStrategy
from ntquant.strategies.roc_momentum import RocMomentumConfig, RocMomentumStrategy
from ntquant.strategies.rsi_reversal import RsiReversalConfig, RsiReversalStrategy

STRATEGIES: dict[str, tuple[type[BaseStrategyConfig], type[BaseStrategy]]] = {
    "ema_cross": (EMACrossConfig, EMACrossStrategy),
    "rsi_reversal": (RsiReversalConfig, RsiReversalStrategy),
    "bollinger_reversal": (BollingerReversalConfig, BollingerReversalStrategy),
    "roc_momentum": (RocMomentumConfig, RocMomentumStrategy),
    "macd_cross": (MacdCrossConfig, MacdCrossStrategy),
}

ALIASES = {
    "ema": "ema_cross",
    "emacross": "ema_cross",
    "rsi": "rsi_reversal",
    "bollinger": "bollinger_reversal",
    "bb": "bollinger_reversal",
    "roc": "roc_momentum",
    "macd": "macd_cross",
}

SUPPORTED_STRATEGIES = tuple(sorted(STRATEGIES.keys() | ALIASES.keys()))


def canonical(name: str) -> str:
    """Resolve a strategy name or alias to its registered name."""
    key = name.lower()
    return ALIASES.get(key, key)


def build_strategy(
    config: BacktestConfig,
    name: str | None = None,
    params: dict[str, Any] | None = None,
) -> BaseStrategy:
    """Construct a configured strategy, applying explicit parameter overrides."""
    selected = canonical(name or config.strategy.name)
    if selected not in STRATEGIES:
        raise ValueError(
            f"Unknown strategy '{selected}'. Registered: {sorted(STRATEGIES)}"
        )

    config_type, strategy_type = STRATEGIES[selected]
    fields = set(config_type.__struct_fields__) - {
        "instrument_id", "bar_type", "trade_size", "strategy_id"
    }
    stored = (
        config.strategy.params
        if selected == canonical(config.strategy.name)
        else {}
    )
    overrides = dict(params or {})
    trade_size = str(overrides.pop("trade_size", config.strategy.trade_size))
    invalid = (set(stored) | set(overrides)) - fields
    if invalid:
        raise ValueError(f"Unknown parameters for '{selected}': {sorted(invalid)}")

    values = dict(stored)
    values.update(overrides)
    strategy_config = config_type(
        instrument_id=InstrumentId.from_str(config.instrument.instrument_id),
        bar_type=make_bar_type(config.strategy.bar_type),
        trade_size=trade_size,
        strategy_id=config.strategy.strategy_id,
        **values,
    )
    return strategy_type(strategy_config)
