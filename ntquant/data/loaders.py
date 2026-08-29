"""External data loader placeholders.

These are stubs for future real data ingestion (e.g. Binance K-lines, Databento).
Implement one set of functions per provider, returning Nautilus Bar objects,
then route them through :class:`ntquant.data.catalog.DataCatalog`.
"""
from __future__ import annotations

from typing import Protocol


class BarLoader(Protocol):
    """Protocol for a bar loader/fetcher."""

    def load(self, **kwargs) -> list:
        """Return a list of Nautilus Bar objects."""
        ...


class BinanceKlineLoader:
    """Placeholder for Binance K-line loading (not implemented)."""

    def load(self, **kwargs) -> list:  # pragma: no cover
        raise NotImplementedError("BinanceKlineLoader is a placeholder; wire in real auth/data.")
