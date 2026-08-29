"""External data source loaders.

Each source produces a raw OHLCV ``pd.DataFrame`` which is then normalised by
``ntquant.data.schema`` and converted to Nautilus ``Bar`` objects before being
written to the ``ParquetDataCatalog`` (see ``ntquant.data.ingest``).

Sources receive the full :class:`ntquant.config.BacktestConfig` so they can read
both ``config.instrument`` (raw symbol, precision) and ``config.data``
(``source_path``, ``bar_type``, ``columns``, ``tz``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from ntquant.config import BacktestConfig
from ntquant.data.schema import normalize_ohlcv_frame


class BarSource(Protocol):
    """Protocol for an external OHLCV source."""

    def load(self, config: BacktestConfig, **kwargs: Any) -> Any:
        """Return a raw OHLCV ``pd.DataFrame``."""
        ...


class CsvSource:
    """Load local CSV/Parquet OHLCV files into a raw DataFrame.

    Reads ``config.data.source_path`` (a file path, no directories). Use
    ``config.data.columns`` to map arbitrary source column names to the canonical
    ones, e.g. ``{"Date": "timestamp", "Open": "open", ...}``.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._default_path = Path(path) if path else None

    def load(self, config: BacktestConfig, **kwargs: Any) -> Any:
        import pandas as pd

        path = Path(kwargs.get("path", self._default_path) or config.data.source_path)
        if path is None:
            raise ValueError("CsvSource needs data.source_path (config or constructor)")
        if not path.exists():
            raise FileNotFoundError(f"CSV/Parquet source not found: {path}")

        if path.suffix.lower() in (".parquet", ".pq"):
            df = pd.read_parquet(path)
        else:
            df = pd.read_csv(path)
        return normalize_ohlcv_frame(
            df,
            tz=config.data.tz,
            columns=config.data.columns,
            timestamp_col=config.data.timestamp_col,
        )


class BinanceKlineSource:
    """Load historical klines from Binance's public REST API (no auth).

    Uses ``/api/v3/klines`` for the spot market. The symbol is derived from
    ``instrument.raw_symbol`` (e.g. ``"BTC/USDT"`` -> ``"BTCUSDT"``) and the
    interval from the bar type aggregation (e.g. ``1-MINUTE`` -> ``"1m"``).
    """

    BASE_URL = "https://api.binance.com/api/v3/klines"

    # Nautilus aggregation name -> Binance interval string.
    _INTERVAL_MAP = {
        "1-MINUTE": "1m",
        "5-MINUTE": "5m",
        "15-MINUTE": "15m",
        "30-MINUTE": "30m",
        "1-HOUR": "1h",
        "4-HOUR": "4h",
        "1-DAY": "1d",
        "1-WEEK": "1w",
    }

    def __init__(self, timeout: float = 30.0, limit: int = 1000) -> None:
        self.timeout = timeout
        self.limit = limit

    def _interval(self, bar_type) -> str:
        # BarType string form: ``{instrument_id}-{step}-{unit}-{price_type}-EXTERNAL``,
        # e.g. ``"BTCUSDT.BINANCE-1-HOUR-LAST-EXTERNAL"``. The aggregation is the
        # ``{step}-{unit}`` token (e.g. ``1-HOUR``), which a plain ``split("-")``
        # cannot recover because step and unit land in separate tokens.
        import re

        text = str(bar_type)
        match = re.search(r"(\d+)-(SECOND|MINUTE|HOUR|DAY|WEEK|MONTH)", text)
        if not match:
            raise ValueError(
                f"Cannot derive a Binance interval from bar type '{bar_type}'. "
                f"Supported aggregations: {', '.join(sorted(self._INTERVAL_MAP))}"
            )
        agg = f"{match.group(1)}-{match.group(2)}"
        if agg not in self._INTERVAL_MAP:
            supported = ", ".join(sorted(self._INTERVAL_MAP))
            raise ValueError(
                f"Unsupported bar aggregation '{agg}' for Binance. Supported: {supported}"
            )
        return self._INTERVAL_MAP[agg]

    def _symbol(self, instrument) -> str:
        raw = getattr(instrument, "raw_symbol", None)
        if not raw:
            raise ValueError(
                "BinanceKlineSource needs instrument.raw_symbol (e.g. 'BTC/USDT')"
            )
        return "".join(ch for ch in raw if ch.isalnum()).upper()

    def _fetch(self, url: str) -> list:
        import json
        import urllib.request

        req = urllib.request.Request(url, headers={"User-Agent": "ntquant/0.1"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def load(self, config: BacktestConfig, **kwargs: Any) -> Any:
        import pandas as pd

        bar_type_str = kwargs.get("bar_type") or config.data.bar_type
        limit = int(kwargs.get("limit", self.limit))
        symbol = self._symbol(config.instrument)
        interval = self._interval(bar_type_str)

        url = f"{self.BASE_URL}?symbol={symbol}&interval={interval}&limit={limit}"
        rows = self._fetch(url)

        # Binance kline:
        # [open_time(ms), open, high, low, close, volume, close_time, quote_volume,
        #  trades, taker_base, taker_quote, ignore]
        cols = [
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_base", "taker_quote", "ignore",
        ]
        df = pd.DataFrame(rows, columns=cols)
        price_cols = ["open", "high", "low", "close", "volume"]
        for col in price_cols:
            df[col] = df[col].astype(float)
        df["ts"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df = df.set_index("ts")
        df = df.drop(columns=["open_time", "close_time"], errors="ignore")
        return normalize_ohlcv_frame(df, tz=config.data.tz)


class KeyedDataProvider:
    """Base for key-required, not-yet-wired providers (Polygon/Tiingo/Databento)."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    def _require_key(self) -> None:
        if not self.api_key:
            raise NotImplementedError(
                f"{self.__class__.__name__} requires an API key; no provider is wired yet. "
                "Set the key via `NTA_*` env or adapt this class to the provider SDK."
            )


class PolygonSource(KeyedDataProvider):
    """Placeholder for Polygon.io stocks/FX bars (requires api key)."""

    def load(self, config: BacktestConfig, **kwargs: Any) -> Any:
        self._require_key()
        raise NotImplementedError("PolygonSource is not implemented yet.")


class AlphaVantageSource(KeyedDataProvider):
    """Placeholder for Alpha Vantage bar data (requires api key)."""

    def load(self, config: BacktestConfig, **kwargs: Any) -> Any:
        self._require_key()
        raise NotImplementedError("AlphaVantageSource is not implemented yet.")


class DatabentoSource(KeyedDataProvider):
    """Placeholder for Databento commercial data (requires api key)."""

    def load(self, config: BacktestConfig, **kwargs: Any) -> Any:
        self._require_key()
        raise NotImplementedError("DatabentoSource is not implemented yet.")


_SOURCE_REGISTRY: dict[str, type[BarSource]] = {
    "csv": CsvSource,
    "parquet": CsvSource,
    "binance": BinanceKlineSource,
    "polygon": PolygonSource,
    "alphavantage": AlphaVantageSource,
    "databento": DatabentoSource,
}


def get_source(name: str, **kwargs: Any) -> BarSource:
    """Build a source instance by name, injecting kwargs."""
    key = name.lower()
    if key not in _SOURCE_REGISTRY:
        raise ValueError(f"Unknown data source '{name}'. Available: {sorted(_SOURCE_REGISTRY)}")
    return _SOURCE_REGISTRY[key](**kwargs)


__all__ = [
    "BarSource",
    "CsvSource",
    "BinanceKlineSource",
    "PolygonSource",
    "AlphaVantageSource",
    "DatabentoSource",
    "get_source",
]
