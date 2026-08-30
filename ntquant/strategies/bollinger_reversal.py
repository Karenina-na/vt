"""Bollinger-Band mean-reversion factor (standard Strategy subclass).

Buys when price closes below the lower band, sells/shorts above the upper band,
reverting to the middle band. A volatility-scaled contra-trend signal.
"""
from __future__ import annotations

from nautilus_trader.indicators import BollingerBands
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide

from ntquant.strategies.base import BaseStrategy, BaseStrategyConfig


class BollingerReversalConfig(BaseStrategyConfig):
    """Configuration for the Bollinger mean-reversion factor (msgspec-annotated)."""

    period: int = 20
    num_std: float = 2.0


class BollingerReversalStrategy(BaseStrategy):
    """Bollinger mean-reversion: fade closes below lower / above upper band."""

    def __init__(self, config: BollingerReversalConfig) -> None:
        super().__init__(config)
        self.bbands = BollingerBands(config.period, config.num_std)

    def on_start(self) -> None:
        super().on_start()
        if self.instrument is None:
            return
        self.register_indicator_for_bars(self.config.bar_type, self.bbands)

    def on_bar(self, bar: Bar) -> None:
        if not self.indicators_initialized():
            return

        config = self.config
        instrument_id = config.instrument_id
        trade_size = config.trade_size
        close = bar.close.as_double()
        upper = self.bbands.upper
        lower = self.bbands.lower

        if self.portfolio.is_flat(instrument_id):
            if close < lower:
                self.log.info(f"Close {close:.2f} < lower {lower:.2f}: BUY (mean-revert)")
                self.submit_market(OrderSide.BUY, trade_size)
            elif close > upper:
                self.log.info(f"Close {close:.2f} > upper {upper:.2f}: SELL (mean-revert)")
                self.submit_market(OrderSide.SELL, trade_size)
