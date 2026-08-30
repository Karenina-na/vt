"""MACD momentum factor (standard Strategy subclass).

In 1.231.0 ``nautilus_trader.indicators.MovingAverageConvergenceDivergence`` is
broken (its internal signal EMA is never constructed, so updates raise
``AttributeError: 'NoneType' object has no attribute 'update_raw'``). This factor
therefore computes the MACD line from two EMAs directly and derives a signal by
feeding an EMA of the MACD line, then trades the signal line's zero-crossing:
long above zero, short below zero.
"""
from __future__ import annotations

from nautilus_trader.indicators import ExponentialMovingAverage
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide

from ntquant.strategies.base import BaseStrategy, BaseStrategyConfig


class MacdCrossConfig(BaseStrategyConfig):
    """Configuration for the MACD momentum factor (msgspec-annotated)."""

    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9


class MacdCrossStrategy(BaseStrategy):
    """MACD momentum via a hand-built MACD + signal EMA (zero-crossing)."""

    def __init__(self, config: MacdCrossConfig) -> None:
        super().__init__(config)
        self.fast_ema = ExponentialMovingAverage(config.fast_period)
        self.slow_ema = ExponentialMovingAverage(config.slow_period)
        self.signal_ema = ExponentialMovingAverage(config.signal_period)

    def on_start(self) -> None:
        super().on_start()
        if self.instrument is None:
            return
        # fast/slow EMA fed from bars; signal EMA is fed manually with the macd line.
        self.register_indicator_for_bars(self.config.bar_type, self.fast_ema)
        self.register_indicator_for_bars(self.config.bar_type, self.slow_ema)

    def on_bar(self, bar: Bar) -> None:
        if not self.indicators_initialized():
            return

        instrument_id = self.config.instrument_id
        trade_size = self.config.trade_size

        # MACD line = fast EMA - slow EMA. Feed the signal EMA with that value so
        # the EMA indicator initialized mirrors the signal line.
        macd_line = self.fast_ema.value - self.slow_ema.value
        self.signal_ema.update_raw(macd_line)
        if not self.signal_ema.initialized:
            return

        signal = self.signal_ema.value

        if self.portfolio.is_flat(instrument_id):
            if signal > 0:
                self.log.info(f"MACD signal {signal:.4f} > 0: BUY (bullish)")
                self.submit_market(OrderSide.BUY, trade_size)
            elif signal < 0:
                self.log.info(f"MACD signal {signal:.4f} < 0: SELL (bearish)")
                self.submit_market(OrderSide.SELL, trade_size)
