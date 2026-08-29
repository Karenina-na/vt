"""Multi-strategy base classes for ntquant.

Credits: 1.231.0's ``StrategyConfig`` is a frozen msgspec ``Struct``. Extending
it with custom fields requires **type-annotation fields** (msgspec style), not
the ``__init__``/``__new__`` + ``_CUSTOM_FIELDS`` pattern shown in the `latest`
docs (that pattern raises TypeError in 1.231.0).
"""
from __future__ import annotations

from decimal import Decimal

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Quantity
from nautilus_trader.trading import Strategy


class BaseStrategyConfig(StrategyConfig):
    """Common typed fields shared by all ntquant strategies.

    Subclasses add their own annotated fields (msgspec-style). Keep ``strategy_id``
    unique per instance and provide ``order_id_tag`` to keep client order IDs unique.
    """

    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: str


class BaseStrategy(Strategy):
    """Common helper behaviour for trend/level style strategies.

    Subclasses implement ``on_bar``/``on_quote`` etc. and call the inherited
    helpers for order submission.
    """

    def __init__(self, config: BaseStrategyConfig) -> None:
        super().__init__(config)

    def on_start(self) -> None:
        """Resolve the instrument, register indicators, and subscribe to bars.

        Subclasses should call ``super().on_start()`` first, then register any
        custom indicators and subscribe to data.
        """
        self.instrument = self.cache.instrument(self.config.instrument_id)
        if self.instrument is None:
            self.log.error(f"Instrument not found: {self.config.instrument_id}")
            self.stop()
            return
        self.subscribe_bars(self.config.bar_type)

    def submit_market(self, side: OrderSide, size: str | Decimal) -> None:
        """Submit a market order using the strategy's OrderFactory.

        The size is normalised to the instrument's ``size_precision`` (via
        ``make_qty``), so raw strings such as ``"10000"`` work even when the
        instrument declares a size precision of 2.
        """
        quantity = Quantity.from_str(str(size))
        if self.instrument is not None:
            quantity = self.instrument.make_qty(quantity)
        order = self.order_factory.market(
            instrument_id=self.config.instrument_id,
            order_side=side,
            quantity=quantity,
        )
        self.submit_order(order)

    def on_stop(self) -> None:
        """Cancel all orders and close all positions on strategy stop."""
        self.log.info("Strategy stopping: cancel all orders, flatten positions")
        self.cancel_all_orders(self.config.instrument_id)
        self.close_all_positions(self.config.instrument_id)
