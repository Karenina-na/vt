"""Unified OHLCV DataFrame schema for external data ingestion.

All real-data sources are normalised to a common pandas DataFrame before being
converted to Nautilus ``Bar`` objects via ``BarDataWrangler`` (which expects a
``DatetimeIndex`` plus ``open``/``high``/``low``/``close``/``volume`` columns).
"""

from __future__ import annotations

import pandas as pd

OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")

# Common aliases seen across public sources -> canonical column name.
_COLUMN_ALIASES = {
    "timestamp": None,  # handled separately (index)
    "time": None,
    "datetime": None,
    "date": None,
    "open_time": None,
    "open": "open",
    "o": "open",
    "high": "high",
    "h": "high",
    "low": "low",
    "l": "low",
    "close": "close",
    "c": "close",
    "volume": "volume",
    "v": "volume",
    "vol": "volume",
    "base_volume": "volume",
    "quote_volume": None,  # ignored
    "trades": None,  # ignored
}


def normalize_ohlcv_frame(
    data: pd.DataFrame,
    tz: str = "UTC",
    columns: dict[str, str] | None = None,
    timestamp_col: str | None = None,
) -> pd.DataFrame:
    """Return a canonical OHLCV DataFrame with a UTC ``DatetimeIndex``.

    Args:
        data: Raw OHLCV frame (any column names / ordering).
        tz: Timezone to apply/convert to (defaults to UTC).
        columns: Explicit map of ``{raw_column: canonical_column}``. Overrides the
            built-in alias table (e.g. ``{"Date": "timestamp", "Open": "open"}``).
        timestamp_col: Column name holding the timestamp if it is not the index.

    Returns:
        A frame indexed by ``DatetimeIndex`` (UTC, ascending, duplicates removed)
        with exactly the canonical OHLCV columns.

    Raises:
        ValueError: If required OHLCV columns are missing after the mapping.
    """
    df = data.copy()

    mapping: dict[str, str] = dict(columns or {})
    if timestamp_col:
        mapping[timestamp_col] = "timestamp"

    # Apply explicit overrides first, then aliases for unmapped columns.
    renamed: dict[str, str] = {}
    for col in df.columns:
        target = mapping.get(col)
        if target is None:
            target = _COLUMN_ALIASES.get(col, _COLUMN_ALIASES.get(str(col).lower()))
        if target and target != col:
            renamed[col] = target
    df = df.rename(columns=renamed)

    if "timestamp" in df.columns:
        df = df.set_index("timestamp")
    if not isinstance(df.index, pd.DatetimeIndex):
        try:
            df.index = pd.to_datetime(df.index)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            raise ValueError(f"Timestamp index is not datetime-convertible: {exc}") from exc

    missing = [c for c in OHLCV_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing OHLCV columns after mapping: {missing}")

    df = df[list(OHLCV_COLUMNS)]
    df.index = df.index.tz_convert(tz) if df.index.tz is not None else df.index.tz_localize(tz)
    df.index.name = "timestamp"
    df = df[~df.index.duplicated(keep="first")].sort_index()
    return df
