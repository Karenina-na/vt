"""RSI mean-reversion factor (standard Strategy subclass).

Buys when RSI dips below ``oversold`` (from flat) and sells/shorts when RSI
rises above ``overbought``. This is the canonical non-trending example; its
signals are opposite in character to the EMA-cross trend factor.
"""
from __future__ import annotations

from nautilus_trader.indicators import RelativeStrengthIndex
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide

from ntquant.strategies.base import BaseStrategy, BaseStrategyConfig


class RsiReversalConfig(BaseStrategyConfig):
    """Configuration for the RSI mean-reversion factor (msgspec-annotated)."""

    period: int = 14
    oversold: float = 30.0
    overbought: float = 70.0


class RsiReversalStrategy(BaseStrategy):
    """RSI mean-reversion: buy oversold, sell overbought (from flat)."""

    def __init__(self, config: RsiReversalConfig) -> None:
        super().__init__(config)
        self.rsi = RelativeStrengthIndex(config.period)

    def on_start(self) -> None:
        super().on_start()
        if self.instrument is None:
            return
        self.register_indicator_for_bars(self.config.bar_type, self.rsi)

    def on_bar(self, bar: Bar) -> None:
        if not self.indicators_initialized():
            return

        config = self.config
        instrument_id = config.instrument_id
        trade_size = config.trade_size
        rsi = self.rsi.value

        if self.portfolio.is_flat(instrument_id):
            if rsi < config.oversold:
                self.log.info(f"RSI oversold {rsi:.2f}->{config.oversold}: BUY")
                self.submit_market(OrderSide.BUY, trade_size)
            elif rsi > config.overbought:
                self.log.info(f"RSI overbought {rsi:.2f}->{config.overbought}: SELL")
                self.submit_market(OrderSide.SELL, trade_size)
