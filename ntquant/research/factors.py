"""Strategy (factor) registry for research evaluation.

A "factor" is a standard Nautilus ``Strategy`` subclass (registered here together
with its ``StrategyConfig``). Adding a new factor means subclassing
``BaseStrategy``/``BaseStrategyConfig`` and registering it in both the
``STRATEGY_CONFIGS`` map and ``FACTOR_BUILDERS``/``FACTORY_CONFIGS``.
"""
from __future__ import annotations

from ntquant.backtest.runner import STRATEGY_CONFIGS
from ntquant.strategies.base import BaseStrategy, BaseStrategyConfig
from ntquant.strategies.ema_cross import EMACrossConfig, EMACrossStrategy

# Factor name -> Strategy class (used by the research runner to instantiate).
FACTORY_CONFIGS: dict[str, type[BaseStrategyConfig]] = {
    "ema_cross": EMACrossConfig,
}
FACTOR_BUILDERS: dict[str, type[BaseStrategy]] = {
    "ema_cross": EMACrossStrategy,
}

# Aliases for convenience (snake_case variants).
ALIASES = {"ema": "ema_cross", "emacross": "ema_cross"}

SUPPORTED_FACTORS = tuple(
    sorted(set(FACTORY_CONFIGS) | set(STRATEGY_CONFIGS) | set(ALIASES))
)


def canonical(name: str) -> str:
    """Resolve a factor name (or alias) to its canonical key."""
    key = name.lower()
    return ALIASES.get(key, key)


def build_strategy(name: str, config) -> BaseStrategy:
    """Instantiate a configured strategy by factor name."""
    key = canonical(name)
    builder = FACTOR_BUILDERS.get(key)
    if builder is None:
        raise ValueError(
            f"Unknown factor '{name}'. Registered: {sorted(FACTOR_BUILDERS)}"
        )
    return builder(config)


__all__ = [
    "SUPPORTED_FACTORS",
    "FACTOR_BUILDERS",
    "FACTORY_CONFIGS",
    "canonical",
    "build_strategy",
]
