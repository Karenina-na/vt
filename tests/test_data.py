"""Tests for data generation and catalog persistence."""
import pytest

from ntquant.backtest.instruments import make_bar_type
from ntquant.data.catalog import DataCatalog
from ntquant.data.synthetic import generate_synthetic_bars


def test_generate_bars_ohlc_invariant():
    bt = make_bar_type("EUR/USD.SIM-1-MINUTE-LAST-EXTERNAL")
    bars = generate_synthetic_bars(bt, count=200, seed=42)
    assert len(bars) == 200
    for b in bars:
        assert b.low <= b.open <= b.high
        assert b.low <= b.close <= b.high


def test_generate_bars_seed_reproducible():
    bt = make_bar_type("EUR/USD.SIM-1-MINUTE-LAST-EXTERNAL")
    a = generate_synthetic_bars(bt, count=50, seed=1)
    b = generate_synthetic_bars(bt, count=50, seed=1)
    assert [x.close.as_double() for x in a] == [x.close.as_double() for x in b]


def test_catalog_roundtrip(tmp_path):
    bt = make_bar_type("EUR/USD.SIM-1-MINUTE-LAST-EXTERNAL")
    bars = generate_synthetic_bars(bt, count=100, seed=3)
    cat = DataCatalog(tmp_path)
    cat.write_bars(bars)
    loaded = cat.load_bars(bt.instrument_id, bt)
    assert len(loaded) == 100
