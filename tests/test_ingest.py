"""Tests for the ingestion pipeline and runner real-source paths."""
import pandas as pd
import pytest

from ntquant.backtest.instruments import make_bar_type
from ntquant.config import load_backtest_config
from ntquant.data.ingest import ingest
from ntquant.data.loaders import CsvSource


def _csv_config(tmp_path, source_key="csv"):
    csv = tmp_path / "bars.csv"
    rows = []
    for i in range(30):
        rows.append(
            f"2026-01-01T00:{i:02d}:00Z,{1.0 + i*0.01},{1.2 + i*0.01},{0.9 + i*0.01},"
            f"{1.1 + i*0.01},1000"
        )
    csv.write_text("time,open,high,low,close,volume\n" + "\n".join(rows) + "\n")

    cfg = load_backtest_config()
    return cfg.__class__(
        venue=cfg.venue,
        instrument=cfg.instrument,
        strategy=cfg.strategy,
        data=cfg.data.__class__(
            instrument_id=cfg.data.instrument_id,
            catalog_path=str(tmp_path / "catalog"),
            bar_type=cfg.data.bar_type,
            source=source_key,
            source_path=str(csv),
            tz="UTC",
            timestamp_col="time",
        ),
        output_path=cfg.output_path,
        log_level=cfg.log_level,
    )


def test_ingest_writes_catalog(tmp_path):
    cfg = _csv_config(tmp_path)
    outcome = ingest(cfg)
    assert outcome.bars == 30
    assert outcome.instruments == 1
    assert outcome.merged is True

    # data is now readable from the catalog for a backtest/analysis path.
    from ntquant.data.catalog import DataCatalog

    cat = DataCatalog(cfg.data.catalog_path)
    bt = make_bar_type(cfg.data.bar_type)
    loaded = cat.load_bars(bt.instrument_id, bt)
    assert len(loaded) == 30


def test_ingest_rejects_synthetic(tmp_path):
    cfg = _csv_config(tmp_path)
    from ntquant.config import DataConfig

    cfg = cfg.__class__(
        venue=cfg.venue, instrument=cfg.instrument, strategy=cfg.strategy,
        data=cfg.data.__class__(
            instrument_id=cfg.data.instrument_id,
            catalog_path=cfg.data.catalog_path,
            bar_type=cfg.data.bar_type,
            source="synthetic",
            source_path=cfg.data.source_path,
        ),
        output_path=cfg.output_path, log_level=cfg.log_level,
    )
    with pytest.raises(ValueError, match="Cannot ingest from 'synthetic'"):
        ingest(cfg)


def test_runner_reads_catalog_for_real_source(tmp_path, monkeypatch):
    # When data.source is a real source, the runner must read from the catalog
    # (not synthetic), even without the --catalog flag.
    from ntquant.backtest.runner import _load_bars, run_backtest

    cfg = _csv_config(tmp_path)
    ingest(cfg)
    bt = make_bar_type(cfg.data.bar_type)
    bars = _load_bars(cfg, bt, use_catalog=False)
    assert len(bars) == 30
    assert bars[0].open.as_double() == pytest.approx(1.0)


def test_runner_raises_if_real_source_empty(tmp_path):
    from ntquant.backtest.runner import _load_bars

    cfg = _csv_config(tmp_path)  # source=csv but catalog empty
    bt = make_bar_type(cfg.data.bar_type)
    with pytest.raises(ValueError, match="Run `ntquant ingest"):
        _load_bars(cfg, bt, use_catalog=False)


def test_round_to_instrument_precision():
    # Real data may carry more decimals than the instrument precision; the frame
    # must be rounded so BarDataWrangler accepts it.
    from ntquant.backtest.instruments import make_instrument
    from ntquant.data.ingest import _round_to_instrument

    cfg = load_backtest_config()
    inst = make_instrument(cfg)
    df = pd.DataFrame({
        "open": [2451.80001],
        "high": [2454.29001],
        "low": [2446.68001],
        "close": [2447.30001],
        "volume": [18893.89001],
    }, index=pd.DatetimeIndex(["2026-01-01T00:00:00Z"], tz="UTC"))
    out = _round_to_instrument(df, inst)
    # price_precision=2, size_precision=3
    assert out["close"].iloc[0] == pytest.approx(2447.30, abs=1e-9)
    assert out["volume"].iloc[0] == pytest.approx(18893.890, abs=1e-9)
    # a round-trip through the wrangler now succeeds without read-only errors.
    bar_type = make_bar_type(cfg.data.bar_type)
    from nautilus_trader.persistence.wranglers import BarDataWrangler

    bars = BarDataWrangler(bar_type, inst).process(out)
    assert len(bars) == 1


def _kline_page(start_ms, span_ms=15 * 60 * 1000, count=3):
    """Synthesize a page of Binance klines starting at start_ms (ascending)."""
    rows = []
    for i in range(count):
        t = start_ms + i * span_ms
        rows.append([t, "1.0", "1.0", "1.0", "1.0", "10.0", t + 599999, "0", 0, "0", "0", "0"])
    return rows


def test_fetch_range_window_pages_forward(monkeypatch):
    # A window larger than chunk size must page forward via startTime cursor.
    from ntquant.data.loaders import BinanceKlineSource

    s = BinanceKlineSource(proxy=None)
    calls = []

    def fake_rows(symbol, interval, limit, start_ms=None, end_ms=None, market=None):
        calls.append(start_ms)
        if start_ms is None:
            return []
        return _kline_page(start_ms, count=limit)

    span = 15 * 60 * 1000  # 15m
    monkeypatch.setattr(s, "_rows", fake_rows, raising=True)
    # 3 pages of limit bars; end beyond the cursor so the loop stops when the
    # returned page is shorter than requested, or end_ms is reached.
    rows = s._fetch_range("ETHUSDT", "15m", 1000, start_ms=1000,
                          end_ms=1000 + 3 * 1000 * span, limit_total=None,
                          market="perpetual")
    assert len(calls) >= 2
    # Cursor must advance monotonically over the pages.
    assert calls == sorted(calls)
    # The rows must be non-empty and ascending.
    assert len(rows) >= 1000


def test_fetch_range_bar_count_pages_backward(monkeypatch):
    # A bar-count (limit_total) request with no window must page backward (newest first).
    from ntquant.data.loaders import BinanceKlineSource

    s = BinanceKlineSource(proxy=None)
    calls = []

    def fake_rows(symbol, interval, limit, start_ms=None, end_ms=None, market=None):
        calls.append(end_ms)
        if end_ms is None:
            return _kline_page(9000, count=limit)
        # Each older page sits just before the endTime cursor.
        return _kline_page(end_ms - limit * span + 1, count=limit)

    span = 15 * 60 * 1000  # 15m
    monkeypatch.setattr(s, "_rows", fake_rows, raising=True)
    rows = s._fetch_range("ETHUSDT", "15m", 1000, start_ms=None, end_ms=None,
                          limit_total=9, market="perpetual")
    assert len(rows) == 9
    # Backward paging: endTime cursor strictly decreases over calls.
    assert calls == sorted(calls, reverse=True)
