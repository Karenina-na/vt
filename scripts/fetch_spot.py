"""Fetch spot (16m/15m) klines for the given symbols and persist to the catalog.

Spot data uses a separate venue (``BINANCE-SPOT``) and ``CurrencyPair``
instrument so it does not collide with the USDT-M perpetual data. Runs against
Binance's public spot endpoint (``/api/v3/klines``).

Usage: python fetch_spot.py <SYMBOL_OR_ALL> [START_YEAR] [START_MONTH]
"""
import dataclasses
import sys
import time

from nautilus_trader.model import Bar
from nautilus_trader.model.currencies import BTC, ETH, SOL, USDT
from nautilus_trader.model.identifiers import InstrumentId, Symbol
from nautilus_trader.model.instruments import CurrencyPair
from nautilus_trader.model.objects import Price, Quantity
from nautilus_trader.persistence.wranglers import BarDataWrangler

from ntquant.backtest.instruments import make_bar_type
from ntquant.config import load_backtest_config
from ntquant.data.catalog import DataCatalog
from ntquant.data.ingest import _round_to_instrument
from ntquant.data.loaders import get_source

BASE = load_backtest_config()
SYMBOLS = {"BTC": (BTC, 2, 6, "60000.00"), "ETH": (ETH, 2, 6, "3500.00"), "SOL": (SOL, 3, 6, "150.00")}


def make_spot_cfg(symbol):
    base_cur, pp, sp, start_px = SYMBOLS[symbol]
    # Venue must be hyphen-free (1.231.0 treats "-SPOT" as an account subtype).
    iid = f"{symbol}USDT.BINANCESPOT"
    raw = f"{symbol}USDT"
    bt = f"{iid}-15-MINUTE-LAST-EXTERNAL"
    # Point the loader's symbol at the spot pair (no "-PERP" -> spot endpoint).
    inst = dataclasses.replace(BASE.instrument, raw_symbol=raw, instrument_id=iid)
    data = dataclasses.replace(BASE.data, instrument_id=iid, bar_type=bt, source="binance")
    strat = dataclasses.replace(BASE.strategy, bar_type=bt, strategy_id=f"SPOT-{symbol}")
    return dataclasses.replace(BASE, instrument=inst, data=data, strategy=strat)


def make_spot_instrument(symbol):
    base_cur, pp, sp, _ = SYMBOLS[symbol]
    return CurrencyPair(
        instrument_id=InstrumentId.from_str(f"{symbol}USDT.BINANCESPOT"),
        raw_symbol=Symbol(f"{symbol}USDT"),
        base_currency=base_cur,
        quote_currency=USDT,
        price_precision=pp,
        size_precision=sp,
        price_increment=Price.from_str(f"{1/10**pp:.{pp}f}"),
        size_increment=Quantity.from_str(f"{1/10**sp:.{sp}f}"),
        lot_size=Quantity.from_int(1),
        max_quantity=Quantity.from_int(10_000_000),
        min_quantity=Quantity.from_str(f"{1/10**sp:.{sp}f}"),
        ts_event=0,
        ts_init=0,
    )


def months(start_year, start_month):
    y, m = start_year, start_month
    out = []
    while (y, m) <= (2026, 8):
        ny, nm = (y, m + 1) if m < 12 else (y + 1, 1)
        e = "2026-08-29T23:59:00Z" if (ny, nm) == (2026, 9) else f"{ny:04d}-{nm:02d}-01T00:00:00Z"
        out.append((f"{y:04d}-{m:02d}-01T00:00:00Z", e))
        y, m = ny, nm
    return out


def fetch(symbol, start_year=2018, start_month=1):
    import pandas as pd
    cfg = make_spot_cfg(symbol)
    instrument = make_spot_instrument(symbol)
    bar_type = make_bar_type(cfg.data.bar_type)
    src = get_source("binance")
    frames = []
    ms = months(start_year, start_month)
    for i, (s, e) in enumerate(ms, 1):
        for attempt in range(8):
            try:
                # Raw symbol with no -PERP -> loader picks the spot endpoint.
                f = src.load(cfg, start=s, end=e)
                if f is not None and len(f):
                    frames.append(f)
                    print(f"[{symbol}] {i}/{len(ms)} {s[:7]} -> {len(f)}", flush=True)
                break
            except Exception as ex:
                print(f"[{symbol}] retry {attempt+1} {s[:7]}: {type(ex).__name__}", flush=True)
                time.sleep(3)
        else:
            print(f"[{symbol}] SKIP {s[:7]}", flush=True)
    frame = pd.concat(frames)
    frame = frame[~frame.index.duplicated(keep="first")].sort_index()
    frame = _round_to_instrument(frame, instrument)
    bars = BarDataWrangler(bar_type, instrument).process(frame)
    catalog = DataCatalog(cfg.data.catalog_path)
    catalog.delete_bars(bar_type)
    catalog.write_data([instrument] + bars)
    catalog.merge_bars(data_cls=Bar, identifier=str(bar_type), deduplicate=True)
    print(f"[{symbol}] SPOT written {len(bars)} bars | {frame.index[0]} -> {frame.index[-1]}", flush=True)


def main():
    target = (sys.argv[1] if len(sys.argv) > 1 else "ALL").upper()
    sy = int(sys.argv[2]) if len(sys.argv) > 2 else 2018
    sm = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    if target == "ALL":
        syms = ["BTC", "ETH", "SOL"]
    elif target in SYMBOLS:
        syms = [target]
    else:
        print(f"Unknown symbol '{target}'. Choose: {list(SYMBOLS)} or ALL")
        sys.exit(1)
    for sym in syms:
        fetch(sym, sy, sm)


if __name__ == "__main__":
    main()
