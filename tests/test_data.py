"""Tests for data generation, catalog persistence, schema and sources."""
import tempfile

import pandas as pd
import pytest

from ntquant.backtest.instruments import make_bar_type, make_instrument
from ntquant.config import load_backtest_config
from ntquant.data.catalog import DataCatalog
from ntquant.data.loaders import BinanceKlineSource, CsvSource, get_source
from ntquant.data.schema import normalize_ohlcv_frame
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


def test_catalog_instruments_roundtrip(tmp_path):
    # 1.231.0 has no ParquetDataCatalog.write_instruments; instruments persist
    # via write_data. Verify the wrapper's write_instruments path and read-back.
    cat = DataCatalog(tmp_path)
    cfg = load_backtest_config()
    cat.write_instruments([make_instrument(cfg)])
    found = cat.list_instruments()
    assert len(found) == 1
    assert str(found[0].id) == cfg.instrument.instrument_id


def test_catalog_has_and_merge(tmp_path):
    bt = make_bar_type("EUR/USD.SIM-1-MINUTE-LAST-EXTERNAL")
    bars = generate_synthetic_bars(bt, count=50, seed=7)
    cat = DataCatalog(tmp_path)
    assert cat.has_bars(bt.instrument_id, bt) is False
    cat.write_bars(bars)
    assert cat.has_bars(bt.instrument_id, bt) is True


def test_normalize_ohlcv_frame_alias_mapping():
    df = pd.DataFrame({
        "Date": ["2026-01-01", "2026-01-01"],
        "Open": [1.0, 1.1],
        "High": [1.2, 1.3],
        "Low": [0.9, 1.0],
        "Close": [1.1, 1.2],
        "Volume": [1000, 1100],
    })
    out = normalize_ohlcv_frame(
        df,
        columns={"Date": "timestamp", "Open": "open", "High": "high",
                 "Low": "low", "Close": "close", "Volume": "volume"},
    )
    assert list(out.columns) == ["open", "high", "low", "close", "volume"]
    assert out.index.tz is not None
    # duplicates removed and sorted ascending
    assert len(out) == 1


def test_normalize_ohlcv_frame_missing_columns():
    df = pd.DataFrame({"open": [1.0], "high": [1.2], "low": [0.9], "close": [1.1]})
    with pytest.raises(ValueError, match="Missing OHLCV"):
        normalize_ohlcv_frame(df)


def test_csv_source_load(tmp_path):
    csv = tmp_path / "bars.csv"
    csv.write_text(
        "time,open,high,low,close,volume\n"
        "2026-01-01T00:00:00Z,1.0,1.2,0.9,1.1,1000\n"
        "2026-01-01T00:01:00Z,1.1,1.3,1.0,1.2,1200\n"
    )
    cfg = load_backtest_config()
    # point source_path at the temp file and give it an explicit timestamp col
    cfg = cfg.__class__(
        venue=cfg.venue, instrument=cfg.instrument, strategy=cfg.strategy,
        data=cfg.data.__class__(
            instrument_id=cfg.data.instrument_id,
            catalog_path=cfg.data.catalog_path,
            bar_type=cfg.data.bar_type,
            source="csv",
            source_path=str(csv),
            tz="UTC",
            timestamp_col="time",
        ),
        output_path=cfg.output_path,
        log_level=cfg.log_level,
    )
    frame = CsvSource().load(cfg)
    assert list(frame.columns) == ["open", "high", "low", "close", "volume"]
    assert len(frame) == 2
    assert frame.index.tz is not None


def test_get_source_resolves_and_validates():
    assert get_source("csv") is not None
    assert get_source("parquet") is not None
    assert get_source("binance") is not None
    with pytest.raises(ValueError, match="Unknown data source"):
        get_source("nope")


def test_binance_interval_and_symbol():
    from ntquant.backtest.instruments import make_instrument
    from ntquant.config import load_backtest_config

    s = BinanceKlineSource()
    assert s._interval("EUR/USD.SIM-1-MINUTE-LAST-EXTERNAL") == "1m"
    assert s._interval("BTC/USDT.SIM-1-HOUR-LAST-EXTERNAL") == "1h"
    assert s._interval("ETHUSDT-PERP.BINANCE-15-MINUTE-LAST-EXTERNAL") == "15m"
    assert s._interval("BTC/USDT.SIM-1-DAY-LAST-EXTERNAL") == "1d"
    # Perpetual raw symbol from the real config maps to the exchange symbol "ETHUSDT".
    cfg = load_backtest_config()
    assert s._symbol(make_instrument(cfg)) == "ETHUSDT"
    with pytest.raises(ValueError, match="Cannot derive"):
        s._interval("EUR/USD.SIM-7-NANOSECOND-LAST-EXTERNAL")


def test_binance_perpetual_symbol_strips_perp():
    # Perpetual raw symbol "ETHUSDT-PERP" must map to the exchange symbol "ETHUSDT".
    from ntquant.config import load_backtest_config
    from ntquant.backtest.instruments import make_instrument

    cfg = load_backtest_config()
    cfg = cfg.__class__(
        venue=cfg.venue, strategy=cfg.strategy,
        data=cfg.data.__class__(
            instrument_id=cfg.data.instrument_id,
            catalog_path=cfg.data.catalog_path,
            bar_type=cfg.data.bar_type,
            source="binance",
        ),
        instrument=cfg.instrument.__class__(
            asset_class="CRYPTOCURRENCY",
            instrument_id="ETHUSDT-PERP.BINANCE",
            raw_symbol="ETHUSDT-PERP",
            base_currency="ETH",
            quote_currency="USDT",
            settlement_currency="USDT",
            price_precision=2,
            size_precision=3,
            price_increment="0.01",
            size_increment="0.001",
            min_quantity="0.001",
            start_price=3500.0,
        ),
    )
    inst = make_instrument(cfg)
    assert BinanceKlineSource()._symbol(inst) == "ETHUSDT"


def test_keyed_providers_raise_without_key():
    from ntquant.data.loaders import PolygonSource
    with pytest.raises(NotImplementedError, match="no provider is wired"):
        PolygonSource().load(load_backtest_config())


def test_binance_fetch_uses_proxy_when_set(monkeypatch):
    import requests

    from ntquant.data.loaders import BinanceKlineSource

    captured = {}

    class _DummyResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return []

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["proxies"] = kwargs.get("proxies")
        return _DummyResp()

    monkeypatch.setattr(requests, "get", fake_get)
    s = BinanceKlineSource(proxy="socks5h://127.0.0.1:1082")
    s._fetch("https://example.com/klines")

    assert captured["proxies"] == {
        "http": "socks5h://127.0.0.1:1082",
        "https": "socks5h://127.0.0.1:1082",
    }


def test_binance_fetch_no_proxy_uses_plain_get(monkeypatch):
    import requests

    from ntquant.data.loaders import BinanceKlineSource

    captured = {}

    class _DummyResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return []

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["proxies"] = kwargs.get("proxies")
        return _DummyResp()

    monkeypatch.setattr(requests, "get", fake_get)
    BinanceKlineSource()._fetch("https://example.com/klines")
    assert captured["proxies"] is None
