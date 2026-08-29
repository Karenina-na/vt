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

    Supports the spot market (``/api/v3/klines``) and the USDT-M futures/perpetual
    market (``/fapi/v1/klines``). ``market`` selects the endpoint and builds the
    Nautilus symbol accordingly: spot ``"BTC/USDT"`` -> ``BTCUSDT`` / perpetual
    ``"BTCUSDT"`` -> ``BTCUSDT`` (no ``-PERP`` suffix in the queried symbol). The
    interval is derived from the bar type aggregation (e.g. ``15-MINUTE`` -> ``"15m"``).
    ``proxy`` is an optional HTTP/HTTPS proxy URL (e.g. ``http://127.0.0.1:7890``).
    """

    BASE_URL = "https://api.binance.com/api/v3/klines"
    BASE_URL_FUTURES = "https://fapi.binance.com/fapi/v1/klines"

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

    def __init__(self, timeout: float = 30.0, limit: int = 1000, market: str = "spot",
                 proxy: str | None = None, chunk_size: int = 1000) -> None:
        self.timeout = timeout
        self.limit = limit
        self.market = market.lower()
        self.proxy = proxy
        self.chunk_size = chunk_size

    @property
    def _base_url(self) -> str:
        return self.BASE_URL_FUTURES if self.market == "perpetual" else self.BASE_URL

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
        raw = str(getattr(instrument, "raw_symbol", "") or "")
        if not raw:
            raise ValueError(
                "BinanceKlineSource needs instrument.raw_symbol (e.g. 'BTC/USDT')"
            )
        # Strip the Nautilus perpetual marker so the queried symbol is the exchange
        # one (e.g. "ETHUSDT-PERP" -> "ETHUSDT" for /fapi/v1/klines).
        if "PERP" in raw.upper():
            raw = raw.split("-")[0]
        return "".join(ch for ch in raw if ch.isalnum()).upper()

    def _fetch(self, url: str, proxy: str | None = None, retries: int = 4) -> list:
        import time

        import requests

        proxy = proxy or self.proxy
        proxies = None
        if proxy:
            # requests[socks] handles http:// https:// and socks5/socks5h://.
            proxies = {"http": proxy, "https": proxy}

        headers = {"User-Agent": "ntquant/0.1"}
        last_exc = None
        for attempt in range(retries):
            try:
                resp = requests.get(url, headers=headers, proxies=proxies, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:  # transient network/proxy errors
                last_exc = exc
                if attempt < retries - 1:
                    time.sleep(1 + attempt)
        raise last_exc

    def _kline_url(self, symbol: str, interval: str, limit: int,
                   start_ms: int | None = None, end_ms: int | None = None,
                   market: str | None = None) -> str:
        base = self.BASE_URL_FUTURES if (market or self.market) == "perpetual" else self.BASE_URL
        url = f"{base}?symbol={symbol}&interval={interval}&limit={limit}"
        if start_ms is not None:
            url += f"&startTime={start_ms}"
        if end_ms is not None:
            url += f"&endTime={end_ms}"
        return url

    def _rows(self, symbol: str, interval: str, limit: int,
              start_ms: int | None = None, end_ms: int | None = None,
              market: str | None = None) -> list:
        return self._fetch(
            self._kline_url(symbol, interval, limit, start_ms, end_ms, market),
            proxy=self.proxy,
        )

    def load(self, config: BacktestConfig, **kwargs: Any) -> Any:
        import pandas as pd

        bar_type_str = kwargs.get("bar_type") or config.data.bar_type
        limit = int(kwargs.get("limit", self.limit))
        symbol = self._symbol(config.instrument)
        interval = self._interval(bar_type_str)
        # Perpetual futures if the raw symbol carries a "-PERP" marker (e.g. "ETHUSDT-PERP").
        market = kwargs.get("market") or self.market
        raw = str(getattr(config.instrument, "raw_symbol", "") or "")
        if "PERP" in raw.upper():
            market = "perpetual"
        # Prefer the config-level proxy (overrides any constructor value).
        if getattr(config.data, "proxy", None):
            self.proxy = config.data.proxy

        # Pagination window: either from an explicit start/end (ms or ISO str) or
        # from a bar count (`limit` treated as 'fetch that many bars' via count).
        start_ms = self._to_ms(kwargs.get("start") or kwargs.get("start_ms"))
        end_ms = self._to_ms(kwargs.get("end") or kwargs.get("end_ms"))
        rows = self._fetch_range(symbol, interval, limit, start_ms, end_ms,
                                 kwargs.get("limit_total"), market)

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

    @staticmethod
    def _to_ms(value) -> int | None:
        """Coerce a ms/ns ISO string or epoch int to milliseconds."""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        import pandas as pd

        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return int(ts.timestamp() * 1000)

    def _fetch_range(self, symbol: str, interval: str, limit: int,
                     start_ms: int | None, end_ms: int | None,
                     limit_total: int | None, market: str | None = None) -> list:
        """Paged fetch over [start_ms, end_ms] or up to ``limit_total`` bars.

        Binance returns at most ``limit`` (<=1000) klines per request. Two paging
        modes:

        - **Window** (``start_ms``/``end_ms`` given): page *forward* from a
          ``startTime`` cursor (``last_open_ms + 1``) until ``end``.
        - **Bar-count** (neither window bound given): page *backward* from the
          latest bar using an ``endTime`` cursor, returning ``limit_total``
          most-recent bars (or ``limit`` when ``limit_total`` is unset).
        """
        all_rows: list = []

        if start_ms is None and end_ms is None:
            # Backward paging: newest bars first, using an endTime cursor.
            total = limit_total if limit_total is not None else limit
            cursor = None
            while len(all_rows) < total:
                page_limit = min(self.chunk_size, total - len(all_rows))
                page = self._rows(symbol, interval, page_limit, None, cursor, market)
                if not page:
                    break
                all_rows.extend(page)
                oldest_open = page[0][0]
                cursor = oldest_open - 1
                if cursor is None:
                    break
                if len(page) < page_limit:
                    break
            # Return chronological ascending.
            return all_rows[:total]

        # Forward window paging: startTime cursor until end_ms.
        total = limit_total if limit_total is not None else None
        cursor = start_ms
        while True:
            page_limit = self.chunk_size if end_ms is not None else min(limit, self.chunk_size)
            page = self._rows(symbol, interval, page_limit, cursor, end_ms, market)
            if not page:
                break
            all_rows.extend(page)

            last_open = page[-1][0]
            cursor = last_open + 1

            if end_ms is not None and cursor > end_ms:
                break
            if total is not None and len(all_rows) >= total:
                break
            if len(page) < page_limit:
                break
            if cursor is None:
                break

        return all_rows[:total] if total is not None else all_rows


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
