"""Build NautilusTrader domain objects (instrument, bar type) from config."""
from __future__ import annotations

from nautilus_trader.model import BarType
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import AssetClass
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import (
    Cfd,
    Commodity,
    CryptoPerpetual,
    CurrencyPair,
    Equity,
    FuturesContract,
    IndexInstrument,
)
from nautilus_trader.model.objects import Price, Quantity

from ntquant.config import BacktestConfig


def make_bar_type(bar_type_str: str) -> BarType:
    """Parse a bar type string into a ``BarType``."""
    return BarType.from_str(bar_type_str)


def _currency(code: str):
    """Resolve a currency code to a Nautilus ``Currency`` (falls back to USD)."""
    from nautilus_trader.model.objects import Currency

    if not code:
        return USD
    try:
        return Currency.from_str(code)
    except Exception:
        return USD


def _asset_class(name: str) -> AssetClass:
    n = name.upper()
    # "FUTURE"/"CFD" are instrument classes, not asset classes.
    if n in ("FUTURE", "FUTURES"):
        return AssetClass.EQUITY
    if n in ("CFD", "SPREAD"):
        return AssetClass.COMMODITY
    member = getattr(AssetClass, n, None)
    if member is None:
        return AssetClass.EQUITY
    return member


def _price(cfg, value: str | None = None):
    return Price.from_str(value or "0.00001")


def make_instrument(config: BacktestConfig):
    """Build the configured instrument, dispatching on ``asset_class``.

    Supports the broadly used Nautilus 1.231.0 instrument classes: FX
    (``CurrencyPair``), EQUITY, CRYPTOCURRENCY (``CryptoPerpetual``),
    futures (``FuturesContract``), INDEX, COMMODITY and CFD. Any unrecognised
    asset class falls back to ``CurrencyPair``.
    """
    inst = config.instrument
    cls_name = inst.asset_class.upper()

    if cls_name == "FX":
        return _make_currency_pair(inst)
    if cls_name == "EQUITY":
        return _make_equity(inst)
    if cls_name in ("CRYPTOCURRENCY", "CRYPTO"):
        return _make_crypto_perpetual(inst)
    if cls_name in ("FUTURE", "FUTURES"):
        return _make_futures_contract(inst)
    if cls_name == "INDEX":
        return _make_index(inst)
    if cls_name == "COMMODITY":
        return _make_commodity(inst)
    if cls_name == "CFD":
        return _make_cfd(inst)
    return _make_currency_pair(inst)


def _make_currency_pair(inst):
    return CurrencyPair(
        instrument_id=InstrumentId.from_str(inst.instrument_id),
        raw_symbol=Symbol(inst.raw_symbol),
        base_currency=_currency(inst.base_currency),
        quote_currency=_currency(inst.quote_currency),
        price_precision=inst.price_precision,
        size_precision=inst.size_precision,
        price_increment=Price.from_str(inst.price_increment),
        size_increment=Quantity.from_str(inst.size_increment),
        lot_size=Quantity.from_int(inst.lot_size),
        max_quantity=Quantity.from_int(inst.max_quantity),
        min_quantity=Quantity.from_str(inst.min_quantity),
        max_price=Price.from_str("10.0"),
        min_price=Price.from_str(inst.price_increment),
        ts_event=0,
        ts_init=0,
    )


def _make_equity(inst):
    return Equity(
        instrument_id=InstrumentId.from_str(inst.instrument_id),
        raw_symbol=Symbol(inst.raw_symbol),
        currency=_currency(inst.base_currency or inst.quote_currency),
        price_precision=inst.price_precision,
        price_increment=Price.from_str(inst.price_increment),
        lot_size=Quantity.from_int(inst.lot_size),
        max_quantity=Quantity.from_int(inst.max_quantity),
        min_quantity=Quantity.from_str(inst.min_quantity),
        ts_event=0,
        ts_init=0,
    )


def _make_crypto_perpetual(inst):
    return CryptoPerpetual(
        instrument_id=InstrumentId.from_str(inst.instrument_id),
        raw_symbol=Symbol(inst.raw_symbol),
        base_currency=_currency(inst.base_currency),
        quote_currency=_currency(inst.quote_currency),
        settlement_currency=_currency(inst.settlement_currency or inst.quote_currency),
        is_inverse=inst.is_inverse,
        price_precision=inst.price_precision,
        size_precision=inst.size_precision,
        price_increment=Price.from_str(inst.price_increment),
        size_increment=Quantity.from_str(inst.size_increment),
        multiplier=Quantity.from_str(inst.multiplier),
        ts_event=0,
        ts_init=0,
    )


def _make_futures_contract(inst):
    return FuturesContract(
        instrument_id=InstrumentId.from_str(inst.instrument_id),
        raw_symbol=Symbol(inst.raw_symbol),
        asset_class=_asset_class(inst.asset_class),
        currency=_currency(inst.quote_currency or inst.base_currency),
        price_precision=inst.price_precision,
        price_increment=Price.from_str(inst.price_increment),
        multiplier=Quantity.from_str(inst.multiplier),
        lot_size=Quantity.from_int(inst.lot_size),
        underlying=inst.underlying or inst.raw_symbol,
        activation_ns=0,
        expiration_ns=0,
        ts_event=0,
        ts_init=0,
    )


def _make_index(inst):
    return IndexInstrument(
        instrument_id=InstrumentId.from_str(inst.instrument_id),
        raw_symbol=Symbol(inst.raw_symbol),
        currency=_currency(inst.quote_currency or inst.base_currency),
        price_precision=inst.price_precision,
        size_precision=inst.size_precision,
        price_increment=Price.from_str(inst.price_increment),
        size_increment=Quantity.from_str(inst.size_increment),
        ts_event=0,
        ts_init=0,
    )


def _make_commodity(inst):
    return Commodity(
        instrument_id=InstrumentId.from_str(inst.instrument_id),
        raw_symbol=Symbol(inst.raw_symbol),
        asset_class=_asset_class(inst.asset_class),
        quote_currency=_currency(inst.quote_currency),
        price_precision=inst.price_precision,
        size_precision=inst.size_precision,
        price_increment=Price.from_str(inst.price_increment),
        size_increment=Quantity.from_str(inst.size_increment),
        ts_event=0,
        ts_init=0,
    )


def _make_cfd(inst):
    return Cfd(
        instrument_id=InstrumentId.from_str(inst.instrument_id),
        raw_symbol=Symbol(inst.raw_symbol),
        asset_class=_asset_class(inst.asset_class),
        quote_currency=_currency(inst.quote_currency),
        price_precision=inst.price_precision,
        size_precision=inst.size_precision,
        price_increment=Price.from_str(inst.price_increment),
        size_increment=Quantity.from_str(inst.size_increment),
        ts_event=0,
        ts_init=0,
    )
