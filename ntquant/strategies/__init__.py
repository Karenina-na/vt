"""Strategy layer: multi-strategy base + concrete strategies."""
from ntquant.strategies.base import BaseStrategy, BaseStrategyConfig
from ntquant.strategies.ema_cross import EMACrossConfig, EMACrossStrategy

__all__ = [
    "BaseStrategy",
    "BaseStrategyConfig",
    "EMACrossConfig",
    "EMACrossStrategy",
]
