"""ParquetDataCatalog wrapper for research data storage."""
from __future__ import annotations

from pathlib import Path

from nautilus_trader.model import Bar
from nautilus_trader.persistence.catalog import ParquetDataCatalog


class DataCatalog:
    """Thin wrapper around ``ParquetDataCatalog`` (nautilus_trader.persistence.catalog).

    Owns a single catalog path and exposes query helpers for bars/instruments.

    Args:
        path: Catalog directory path (auto-created).
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.catalog = ParquetDataCatalog(self.path)

    def write_bars(self, bars: list) -> None:
        """Write Nautilus Bar objects to the catalog."""
        self.catalog.write_data(bars)

    def write_data(self, data: list) -> None:
        """Write arbitrary Nautilus data/instrument objects to the catalog.

        In 1.231.0 the catalog persists instruments together with data through
        ``write_data`` (there is no ``write_instruments`` method). This wrapper
        lets callers write ``[instrument] + bars`` in one pass.
        """
        if data:
            self.catalog.write_data(list(data))

    def write_instruments(self, instruments: list) -> None:
        """Write instrument metadata to the catalog.

        In 1.231.0 ``ParquetDataCatalog`` exposes no ``write_instruments`` method
        (the docs' path raises ``AttributeError``); instruments must be persisted
        together with data via ``write_data``.
        """
        if instruments:
            self.catalog.write_data(list(instruments))

    def load_bars(self, instrument_id, bar_type, start=None, end=None) -> list:
        """Load bars from the catalog, optionally bounded by datetime bounds."""
        start_ns = start.value if hasattr(start, "value") else start
        end_ns = end.value if hasattr(end, "value") else end
        return self.catalog.bars(
            instrument_id=instrument_id,
            bar_type=bar_type,
            start=start_ns,
            end=end_ns,
        )

    def has_bars(self, instrument_id, bar_type) -> bool:
        """Return True if at least one bar exists in the catalog."""
        first = self.catalog.query_first_timestamp(
            data_cls=Bar, identifier=str(bar_type)
        )
        return first is not None

    def merge_bars(self, data_cls: type, identifier: str | None = None,
                   start=None, end=None, deduplicate: bool = True) -> None:
        """Consolidate the catalog's per-file partitions into contiguous files.

        Useful after incremental ingestion to avoid fragmented storage. Pass
        ``data_cls`` (e.g. ``Bar``) so the catalog can resolve the partition path.
        """
        self.catalog.consolidate_data(
            data_cls=data_cls,
            identifier=identifier,
            start=start,
            end=end,
            deduplicate=deduplicate,
        )

    def list_instruments(self) -> list:
        """Return all instrument IDs stored in the catalog."""
        return self.catalog.instruments()
