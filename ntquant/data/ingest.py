"""Ingest external OHLCV data into the ParquetDataCatalog.

Pipeline: source -> normalise -> BarDataWrangler.process -> write_data(catalog).
The resulting catalog can then be consumed by any backtest/analysis/report path
via ``use_catalog=True`` (see ``ntquant.backtest.runner``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nautilus_trader.model import Bar
from nautilus_trader.persistence.wranglers import BarDataWrangler

from ntquant.backtest.instruments import make_bar_type, make_instrument
from ntquant.config import BacktestConfig
from ntquant.data.catalog import DataCatalog
from ntquant.data.loaders import get_source


@dataclass
class IngestOutcome:
    """Result of a successful ingestion run."""

    bars: int
    instruments: int
    catalog_path: str
    bar_type: str
    merged: bool = False

    def summary(self) -> str:
        return (
            f"Ingested {self.bars} bars ({self.bar_type}) into {self.catalog_path}; "
            f"{self.instruments} instrument(s) recorded"
        )


def ingest(config: BacktestConfig, source_name: str | None = None,
           start=None, end=None, limit_total: int | None = None,
           overwrite: bool = False, **source_kwargs) -> IngestOutcome:
    """Fetch, normalise and persist real data for a given backtest config.

    Args:
        config: Backtest configuration (instrument, data, venue).
        source_name: Override ``config.data.source`` when provided.
        start: Optional start of the fetch window (ISO string or ms epoch int).
        end: Optional end of the fetch window (ISO string or ms epoch int).
        limit_total: Optional total number of bars to fetch when a whole window is
            not specified (paged); defaults to a single page.
        overwrite: If True, delete the existing bars for this bar type before
            writing, so re-fetching a window replaces stale/overlapping data instead
            of raising a non-disjoint interval error.
        **source_kwargs: Passed through to ``get_source`` (e.g. ``limit``).

    Returns:
        An :class:`IngestOutcome` describing what was written.
    """
    source_key = (source_name or config.data.source or "synthetic").lower()
    if source_key == "synthetic":
        raise ValueError(
            "Cannot ingest from 'synthetic'; pick a real source "
            "(csv/parquet/binance/polygon/alphavantage/databento)."
        )

    instrument = make_instrument(config)
    bar_type = make_bar_type(config.data.bar_type or config.strategy.bar_type)

    source = get_source(source_key, **source_kwargs)
    load_kwargs = {}
    if start is not None:
        load_kwargs["start"] = start
    if end is not None:
        load_kwargs["end"] = end
    if limit_total is not None:
        load_kwargs["limit_total"] = limit_total
    frame = source.load(config, **load_kwargs)
    if frame is None or len(frame) == 0:
        raise ValueError(f"Source '{source_key}' returned no data.")

    # Real exchange data may carry more decimals than the instrument's precision
    # (e.g. Binance volume with 4dp vs size_precision=3). Round price/volume to
    # the instrument's declared precision so BarDataWrangler accepts the frame.
    frame = _round_to_instrument(frame, instrument)

    bars = BarDataWrangler(bar_type, instrument).process(frame)

    catalog = DataCatalog(config.data.catalog_path)
    if overwrite:
        # Replace stale data to avoid the catalog's non-disjoint interval error.
        catalog.delete_bars(bar_type)
    # 1.231.0: instruments must be persisted with data via write_data.
    catalog.write_data([instrument] + bars)
    catalog.merge_bars(data_cls=Bar, identifier=str(bar_type), deduplicate=True)

    return IngestOutcome(
        bars=len(bars),
        instruments=1,
        catalog_path=str(catalog.path),
        bar_type=str(bar_type),
        merged=True,
    )


def _round_to_instrument(frame, instrument):
    """Round OHLCV values to the instrument's price/size precision.

    ``BarDataWrangler`` rejects frames whose decimal places exceed the
    instrument's ``price_precision``/``size_precision`` (e.g. Binance volume with
    4dp vs ``size_precision=3``). Rounding beforehand keeps real exchange data
    compliant regardless of the source's raw precision.
    """
    import pandas as pd

    df = frame.copy()
    price_cols = ["open", "high", "low", "close"]
    for col in price_cols:
        if col in df.columns:
            df[col] = df[col].round(getattr(instrument, "price_precision", 2))
    if "volume" in df.columns:
        df["volume"] = df["volume"].round(getattr(instrument, "size_precision", 2))
    return df


def ensure_catalog(config: BacktestConfig) -> Path:
    """Return (creating if needed) the catalog directory for a config."""
    catalog = DataCatalog(config.data.catalog_path)
    return catalog.path
