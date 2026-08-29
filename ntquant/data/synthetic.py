"""Synthetic market data generation for backtesting."""
from __future__ import annotations

import numpy as np
import pandas as pd
from nautilus_trader.model import Bar, BarType, Price, Quantity


def generate_synthetic_bars(
    bar_type: BarType,
    count: int = 1000,
    seed: int | None = None,
    start: str = "2026-01-01",
    freq: str = "1min",
    start_price: float = 1.0850,
    price_precision: int = 5,
    volume: str | None = None,
    volume_precision: int | None = None,
) -> list[Bar]:
    """Generate simulated OHLCV bars for backtesting.

    Args:
        bar_type: Target bar type (defines instrument/aggregation).
        count: Number of bars to generate.
        seed: Optional RNG seed for reproducible data.
        start: UTC start timestamp.
        freq: Pandas frequency alias.
        start_price: Initial market price (defaults to a forex-like level).
        price_precision: Decimal places for generated prices (must match the
            instrument's ``price_precision``, e.g. 5 for FX, 2 for crypto/equity).
        volume: Bar volume string; its precision must match ``size_precision``.
            If omitted, ``volume_precision`` is used to build ``"100.xx"``.
        volume_precision: Decimal places for the auto-built volume (matches the
            instrument's ``size_precision``, e.g. 0 for integer sizes).

    Returns:
        A list of Nautilus ``Bar`` objects.
    """
    if volume is None:
        volume = "100" if not volume_precision else f"100.{'0' * volume_precision}"
    rng = np.random.default_rng(seed)
    timestamps = pd.date_range(start, periods=count, freq=freq, tz="UTC")
    price = start_price
    scale = 10 ** (-price_precision)
    fmt = f"{{:.{price_precision}f}}"
    bars: list[Bar] = []
    for ts in timestamps:
        open_px = price
        close_px = open_px + rng.normal(0, scale)
        high_px = max(open_px, close_px) + abs(rng.normal(0, scale))
        low_px = min(open_px, close_px) - abs(rng.normal(0, scale))
        price = close_px

        bars.append(
            Bar(
                bar_type=bar_type,
                open=Price.from_str(fmt.format(open_px)),
                high=Price.from_str(fmt.format(high_px)),
                low=Price.from_str(fmt.format(low_px)),
                close=Price.from_str(fmt.format(close_px)),
                volume=Quantity.from_str(volume),
                ts_event=ts.value,
                ts_init=ts.value,
            )
        )
    return bars
