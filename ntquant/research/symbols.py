"""Symbol/market definitions for research-factor evaluation.

Provides the per-symbol instrument specs and factories to build Nautilus
instruments + bar types for both the USDT-M perpetual (``-PERP``) and Binance
spot (``.BINANCE-SPOT``) markets, matching the catalogs already ingested.
"""
from __future__ import annotations

from dataclasses import dataclass

from nautilus_trader.model.currencies import BTC, ETH, SOL, USDT
from nautilus_trader.model.identifiers import InstrumentId, Symbol
from nautilus_trader.model.instruments import CryptoPerpetual, CurrencyPair
from nautilus_trader.model.objects import Price, Quantity

# symbol -> (base, price_precision, perp_size_precision, spot_size_precision, start_price)
_SYMBOL_META: dict[str, tuple] = {
    "BTC": (BTC, 2, 3, 6, 60_000.0),
    "ETH": (ETH, 2, 3, 6, 3_500.0),
    "SOL": (SOL, 3, 3, 6, 150.0),
}

SUPPORTED_SYMBOLS = tuple(_SYMBOL_META)

_MARKET = ("perp", "spot")


@dataclass(frozen=True)
class SymbolSpec:
    """A tradable symbol on the Binance perp and/or spot venue."""

    symbol: str
    base_currency: object
    price_precision: int
    perp_size_precision: int
    spot_size_precision: int
    start_price: float

    @property
    def quote_currency(self):
        return USDT

    def size_precision(self, market: str) -> int:
        if market == "perp":
            return self.perp_size_precision
        if market == "spot":
            return self.spot_size_precision
        raise ValueError(f"Unknown market '{market}' (expected perp|spot)")

    def instrument_id(self, market: str) -> str:
        if market == "perp":
            return f"{self.symbol}USDT-PERP.BINANCE"
        if market == "spot":
            # Venue names must not contain a hyphen: 1.231.0 treats "-SPOT" as an
            # account subtype, so "BINANCE-SPOT" raises an issuer mismatch.
            return f"{self.symbol}USDT.BINANCESPOT"
        raise ValueError(f"Unknown market '{market}' (expected perp|spot)")

    def bar_type(self, market: str) -> str:
        # Both perp and spot BarTypes use the 15-minute aggregation.
        return f"{self.instrument_id(market)}-15-MINUTE-LAST-EXTERNAL"

    def venue_name(self, market: str) -> str:
        return "BINANCE" if market == "perp" else "BINANCESPOT"


def get_spec(symbol: str) -> SymbolSpec:
    """Return the :class:`SymbolSpec` for a symbol (case-insensitive)."""
    key = symbol.upper()
    if key not in _SYMBOL_META:
        raise ValueError(
            f"Unknown symbol '{symbol}'. Supported: {SUPPORTED_SYMBOLS}"
        )
    base, pp, psp, ssp, start_px = _SYMBOL_META[key]
    return SymbolSpec(key, base, pp, psp, ssp, start_px)


def _price_increment(precision: int) -> str:
    return f"{1 / 10**precision:.{precision}f}"


def build_instrument(spec: SymbolSpec, market: str):
    """Build a Nautilus instrument for a symbol on the given market."""
    size_precision = spec.size_precision(market)
    if market == "perp":
        return CryptoPerpetual(
            instrument_id=InstrumentId.from_str(spec.instrument_id(market)),
            raw_symbol=Symbol(f"{spec.symbol}USDT-PERP"),
            base_currency=spec.base_currency,
            quote_currency=spec.quote_currency,
            settlement_currency=spec.quote_currency,
            is_inverse=False,
            price_precision=spec.price_precision,
            size_precision=size_precision,
            price_increment=Price.from_str(_price_increment(spec.price_precision)),
            size_increment=Quantity.from_str(_price_increment(size_precision)),
            multiplier=Quantity.from_str("1"),
            lot_size=Quantity.from_int(1),
            max_quantity=Quantity.from_int(1_000_000),
            min_quantity=Quantity.from_str(_price_increment(size_precision)),
            ts_event=0,
            ts_init=0,
        )
    if market == "spot":
        return CurrencyPair(
            instrument_id=InstrumentId.from_str(spec.instrument_id(market)),
            raw_symbol=Symbol(f"{spec.symbol}USDT"),
            base_currency=spec.base_currency,
            quote_currency=spec.quote_currency,
            price_precision=spec.price_precision,
            size_precision=size_precision,
            price_increment=Price.from_str(_price_increment(spec.price_precision)),
            size_increment=Quantity.from_str(_price_increment(size_precision)),
            lot_size=Quantity.from_int(1),
            max_quantity=Quantity.from_int(10_000_000),
            min_quantity=Quantity.from_str(_price_increment(size_precision)),
            ts_event=0,
            ts_init=0,
        )
    raise ValueError(f"Unknown market '{market}' (expected perp|spot)")


__all__ = [
    "SUPPORTED_SYMBOLS",
    "SymbolSpec",
    "get_spec",
    "build_instrument",
]
