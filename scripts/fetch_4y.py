"""Fetch 4 years of 15m klines for the given symbols and persist to the catalog.

Usage: python fetch_4y.py <SYMBOL_OR_ALL>   e.g. BTC | ETH | SOL | ALL
"""
import dataclasses, os, sys, time

from ntquant.backtest.instruments import make_bar_type, make_instrument
from ntquant.config import load_backtest_config
from ntquant.data.catalog import DataCatalog
from ntquant.data.ingest import _round_to_instrument
from ntquant.data.loaders import get_source
from nautilus_trader.model import Bar
from nautilus_trader.persistence.wranglers import BarDataWrangler

BASE = load_backtest_config()
SYMBOLS = {"BTC": ("BTC", 2, 3), "ETH": ("ETH", 2, 3), "SOL": ("SOL", 3, 3)}
START_PRICE = {"BTC": 60000.0, "ETH": 3500.0, "SOL": 150.0}


def make_cfg(symbol):
    base, pp, sp = SYMBOLS[symbol]
    iid = f"{symbol}USDT-PERP.BINANCE"
    raw = f"{symbol}USDT-PERP"
    bt = f"{iid}-15-MINUTE-LAST-EXTERNAL"
    pint = f"{1/10**pp:.{pp}f}"
    sint = f"{1/10**sp:.{sp}f}"
    inst = dataclasses.replace(
        BASE.instrument, instrument_id=iid, raw_symbol=raw,
        base_currency=base, quote_currency="USDT", settlement_currency="USDT",
        price_precision=pp, size_precision=sp, price_increment=pint,
        size_increment=sint, min_quantity=sint, start_price=START_PRICE[symbol],
    )
    data = dataclasses.replace(BASE.data, instrument_id=iid, bar_type=bt, source="binance")
    strat = dataclasses.replace(BASE.strategy, bar_type=bt, strategy_id=f"EMA-{symbol}")
    return dataclasses.replace(BASE, instrument=inst, data=data, strategy=strat)


def months():
    y, m = 2022, 9
    out = []
    while (y, m) <= (2026, 8):
        ny, nm = (y, m + 1) if m < 12 else (y + 1, 1)
        e = "2026-08-29T23:59:00Z" if (ny, nm) == (2026, 9) else f"{ny:04d}-{nm:02d}-01T00:00:00Z"
        out.append((f"{y:04d}-{m:02d}-01T00:00:00Z", e))
        y, m = ny, nm
    return out


def fetch(symbol):
    import pandas as pd
    cfg = make_cfg(symbol)
    instrument = make_instrument(cfg)
    bar_type = make_bar_type(cfg.data.bar_type)
    src = get_source("binance")
    frames = []
    ms = months()
    for i, (s, e) in enumerate(ms, 1):
        for attempt in range(4):
            try:
                f = src.load(cfg, start=s, end=e)
                if f is not None and len(f):
                    frames.append(f)
                    print(f"[{symbol}] {i}/{len(ms)} {s[:7]} -> {len(f)}", flush=True)
                break
            except Exception as ex:
                print(f"[{symbol}] retry {attempt+1} {s[:7]}: {type(ex).__name__}", flush=True)
                time.sleep(2)
        else:
            print(f"[{symbol}] SKIP {s[:7]}", flush=True)
    frame = pd.concat(frames)
    frame = frame[~frame.index.duplicated(keep="first")].sort_index()
    frame = _round_to_instrument(frame, instrument)
    bars = BarDataWrangler(bar_type, instrument).process(frame)
    cat = DataCatalog(cfg.data.catalog_path)
    cat.delete_bars(bar_type)
    cat.write_data([instrument] + bars)
    cat.merge_bars(data_cls=Bar, identifier=str(bar_type), deduplicate=True)
    print(f"[{symbol}] written {len(bars)} bars | {frame.index[0]} -> {frame.index[-1]}", flush=True)


def main():
    target = (sys.argv[1] if len(sys.argv) > 1 else "ALL").upper()
    if target == "ALL":
        syms = list(SYMBOLS)
    elif target in SYMBOLS:
        syms = [target]
    else:
        print(f"Unknown symbol '{target}'. Choose: {list(SYMBOLS)} or ALL")
        sys.exit(1)
    for sym in syms:
        fetch(sym)


if __name__ == "__main__":
    main()
