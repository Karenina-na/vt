"""Rate-of-Change momentum factor (standard Strategy subclass).

Enter a long when ROC crosses a positive threshold (momentum building) and a
short when it crosses a negative threshold. Re-entries only from flat.
"""
from __future__ import annotations

from nautilus_trader.indicators import RateOfChange
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide

from ntquant.strategies.base import BaseStrategy, BaseStrategyConfig


class RocMomentumConfig(BaseStrategyConfig):
    """Configuration for the ROC momentum factor (msgspec-annotated)."""

    period: int = 10
    entry_threshold: float = 1.0  # percent; positive -> long, negative -> short


class RocMomentumStrategy(BaseStrategy):
    """ROC momentum: long on strong positive ROC, short on strong negative ROC."""

    def __init__(self, config: RocMomentumConfig) -> None:
        super().__init__(config)
        self.roc = RateOfChange(config.period)

    def on_start(self) -> None:
        super().on_start()
        if self.instrument is None:
            return
        self.register_indicator_for_bars(self.config.bar_type, self.roc)

    def on_bar(self, bar: Bar) -> None:
        if not self.indicators_initialized():
            return

        config = self.config
        instrument_id = config.instrument_id
        trade_size = config.trade_size
        threshold = config.entry_threshold
        roc = self.roc.value * 100.0  # RateOfChange returns a fraction

        if self.portfolio.is_flat(instrument_id):
            if roc > threshold:
                self.log.info(f"ROC {roc:.2f}% > {threshold}%: BUY (momentum)")
                self.submit_market(OrderSide.BUY, trade_size)
            elif roc < -threshold:
                self.log.info(f"ROC {roc:.2f}% < -{threshold}%: SELL (momentum)")
                self.submit_market(OrderSide.SELL, trade_size)
