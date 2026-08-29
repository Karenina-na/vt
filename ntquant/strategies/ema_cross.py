"""EMA crossover strategy (migrated to the BaseStrategy scaffold)."""
from __future__ import annotations

from nautilus_trader.indicators import ExponentialMovingAverage
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide

from ntquant.strategies.base import BaseStrategy, BaseStrategyConfig


class EMACrossConfig(BaseStrategyConfig):
    """Configuration for the EMA cross strategy (msgspec-annotated fields)."""

    fast_period: int = 10
    slow_period: int = 20


class EMACrossStrategy(BaseStrategy):
    """Two moving-average crossover trend-following strategy."""

    def __init__(self, config: EMACrossConfig) -> None:
        super().__init__(config)
        self.fast_ema = ExponentialMovingAverage(config.fast_period)
        self.slow_ema = ExponentialMovingAverage(config.slow_period)

    def on_start(self) -> None:
        """Register EMA indicators and subscribe to bars."""
        super().on_start()
        if self.instrument is None:
            return
        self.register_indicator_for_bars(self.config.bar_type, self.fast_ema)
        self.register_indicator_for_bars(self.config.bar_type, self.slow_ema)
        self.log.info("EMA Cross strategy initialized and subscribed to bars")

    def on_bar(self, bar: Bar) -> None:
        """Compute EMA crossovers and submit orders."""
        if not self.indicators_initialized():
            return

        instrument_id = self.config.instrument_id
        fast_val = self.fast_ema.value
        slow_val = self.slow_ema.value

        is_flat = self.portfolio.is_flat(instrument_id)
        is_net_long = self.portfolio.is_net_long(instrument_id)
        is_net_short = self.portfolio.is_net_short(instrument_id)

        trade_size = self.config.trade_size

        if fast_val > slow_val:
            if is_flat:
                self.log.info(f"Golden cross [BUY]: fast({fast_val:.4f}) > slow({slow_val:.4f})")
                self.submit_market(OrderSide.BUY, trade_size)
            elif is_net_short:
                self.log.info("Short reversed to long: close short then open long")
                self.close_all_positions(instrument_id)
                self.submit_market(OrderSide.BUY, trade_size)

        elif fast_val < slow_val:
            if is_flat:
                self.log.info(f"Death cross [SELL]: fast({fast_val:.4f}) < slow({slow_val:.4f})")
                self.submit_market(OrderSide.SELL, trade_size)
            elif is_net_long:
                self.log.info("Long reversed to short: close long then open short")
                self.close_all_positions(instrument_id)
                self.submit_market(OrderSide.SELL, trade_size)

    def on_order_filled(self, event) -> None:
        """Order fill callback."""
        self.log.info(
            f"Order filled: {event.client_order_id} @ {event.last_px} x {event.last_qty}"
        )
