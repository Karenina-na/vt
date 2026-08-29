"""ParquetDataCatalog wrapper for research data storage."""
from __future__ import annotations

from pathlib import Path

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

    def write_instruments(self, instruments: list) -> None:
        """Write instrument metadata to the catalog."""
        self.catalog.write_instruments(instruments)

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

    def list_instruments(self) -> list:
        """Return all instrument IDs stored in the catalog."""
        return self.catalog.instruments()
