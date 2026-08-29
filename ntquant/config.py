"""Typed configuration loading (YAML + .env).

Precedence (highest first):
1. Environment variables (``NTA_<SECTION>__<KEY>``, loaded from .env).
2. YAML file (user's ``configs/<name>.yaml`` copy or the ``.example`` template).
3. Dataclass field defaults (the single source of config defaults).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Project root = directory containing ``run.py`` / ``pyproject.toml``.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_CONFIG_DIR = _PROJECT_ROOT / "configs"


def _default_config_path(name: str) -> Path:
    """Return the user's config path, falling back to the ``.example`` template.

    A user copy ``configs/<name>.yaml`` takes precedence; if absent the shipped
    ``configs/<name>.example.yaml`` template is used.
    """
    user = _DEFAULT_CONFIG_DIR / f"{name}.yaml"
    if user.exists():
        return user
    return _DEFAULT_CONFIG_DIR / f"{name}.example.yaml"


@dataclass(frozen=True)
class VenueConfig:
    """Simulated venue (single SIM, NETTING + MARGIN)."""

    name: str = "SIM"
    oms_type: str = "NETTING"
    account_type: str = "MARGIN"
    base_currency: str = "USD"
    starting_balance: float = 100_000.0
    default_leverage: int = 10


@dataclass(frozen=True)
class InstrumentConfig:
    """Instrument metadata.

    ``asset_class`` dispatches construction in ``backtest/instruments.py`` to the
    matching Nautilus instrument class (FX/equity/crypto/futures/index/commodity/cfd).
    ``base_currency``/``quote_currency`` are resolved via ``Currency.from_str`` so
    any currency code ("USD", "USDT", "EUR") works, not just USD.
    """

    asset_class: str = "FX"
    instrument_id: str = "EUR/USD.SIM"
    raw_symbol: str = "EUR/USD"
    base_currency: str = "USD"
    quote_currency: str = "USD"
    settlement_currency: str | None = None
    is_inverse: bool = False
    price_precision: int = 5
    size_precision: int = 2
    price_increment: str = "0.00001"
    size_increment: str = "0.01"
    min_quantity: str = "0.01"
    max_quantity: int = 10_000_000
    lot_size: int = 1
    multiplier: str = "1"
    underlying: str | None = None
    start_price: float = 1.0850


@dataclass(frozen=True)
class StrategyConfig:
    """Strategy-level defaults (EMA cross by default).

    ``name`` selects the strategy from the runner registry; ``strategy_id`` gives
    the instance a unique ID (plain string — required by 1.231.0). Extra params
    (``fast_period``, ``slow_period``, ...) are passed through to the strategy
    config; unknown keys are ignored by ``_build``.
    """

    name: str = "ema_cross"
    strategy_id: str = "EMA-001"
    trade_size: str = "10000"
    fast_period: int = 10
    slow_period: int = 30
    bar_type: str = "EUR/USD.SIM-1-MINUTE-LAST-EXTERNAL"


@dataclass(frozen=True)
class DataConfig:
    """Data loading settings.

    ``source`` selects the ingestion source: ``"synthetic"`` (default, generate in
    memory), ``"csv"``/``"parquet"`` (local file via ``source_path``), ``"binance"``
    (public REST), or a keyed provider (Polygon/Tiingo/Databento, placeholders).
    ``columns`` maps arbitrary source column names to the canonical OHLCV ones, and
    ``timestamp_col`` names the source timestamp column when it is not the index.
    ``proxy`` is an HTTP/HTTPS proxy URL (e.g. ``http://127.0.0.1:7890``) used by
    network-based sources (Binance) to reach geoblocked endpoints.
    """

    instrument_id: str = "EUR/USD.SIM"
    count: int = 2000
    seed: int | None = None
    catalog_path: str = "docs/data"
    bar_type: str = "EUR/USD.SIM-1-MINUTE-LAST-EXTERNAL"
    source: str = "synthetic"
    source_path: str | None = None
    tz: str = "UTC"
    columns: dict[str, str] | None = None
    timestamp_col: str | None = None
    proxy: str | None = None


@dataclass(frozen=True)
class BacktestConfig:
    """Top-level backtest configuration."""

    venue: VenueConfig = field(default_factory=VenueConfig)
    instrument: InstrumentConfig = field(default_factory=InstrumentConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    data: DataConfig = field(default_factory=DataConfig)
    output_path: str = "output"
    log_level: str = "INFO"


def _build(dc_type: type, data: dict[str, Any]) -> Any:
    """Build a frozen dataclass from a dict, ignoring unknown keys.

    Missing keys fall through to the dataclass field defaults, so the dataclasses
    are the single source of configuration defaults (no separate defaults dict).
    """
    known = {f for f in dc_type.__dataclass_fields__}
    return dc_type(**{k: v for k, v in data.items() if k in known})


def load_backtest_config(
    path: str | Path | None = None,
    env_prefix: str = "NTA_",
) -> BacktestConfig:
    """Load backtest config from YAML, applying .env overrides.

    ``path`` defaults to the user's ``configs/backtest.yaml`` (or the
    ``backtest.example.yaml`` template when no copy exists). Environment variables
    override YAML keys: ``NTA_STRATEGY_FAST_PERIOD`` etc.
    """
    cfg_path = Path(path) if path else _default_config_path("backtest")
    raw: dict[str, Any] = {}
    if cfg_path.exists():
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    raw = _apply_env_overrides(raw, env_prefix)

    venue = _build(VenueConfig, raw.get("venue", {}))
    instrument = _build(InstrumentConfig, raw.get("instrument", {}))
    strategy = _build(StrategyConfig, raw.get("strategy", {}))
    data = _build(DataConfig, raw.get("data", {}))

    return BacktestConfig(
        venue=venue,
        instrument=instrument,
        strategy=strategy,
        data=data,
        output_path=raw.get("output_path", "output"),
        log_level=raw.get("log_level", "INFO"),
    )


@dataclass(frozen=True)
class ParamScanConfig:
    """Parameter scan configuration."""

    scan: dict[str, list[Any]]
    data: DataConfig = field(default_factory=DataConfig)
    output_path: str = "output"
    log_level: str = "WARNING"


def load_param_config(
    path: str | Path | None = None,
    env_prefix: str = "NTA_",
) -> ParamScanConfig:
    """Load parameter scan config from YAML (.env unused for grids).

    ``path`` defaults to the user's ``configs/param.yaml`` (or the
    ``param.example.yaml`` template when no copy exists).
    """
    cfg_path = Path(path) if path else _default_config_path("param")
    raw: dict[str, Any] = {}
    if cfg_path.exists():
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    data = _build(DataConfig, raw.get("data", {}))
    return ParamScanConfig(
        scan=raw.get("scan", {}),
        data=data,
        output_path=raw.get("output_path", "output"),
        log_level=raw.get("log_level", "WARNING"),
    )


def _apply_env_overrides(raw: dict[str, Any], prefix: str) -> dict[str, Any]:
    """Apply NTA_* env vars onto nested config dict."""
    if not prefix:
        return raw

    section = {"venue": None, "instrument": None, "strategy": None, "data": None}

    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        parts = key[len(prefix):].lower().split("__")
        top = parts[0]
        if top in section:
            nested = section[top]
            if nested is None:
                section[top] = {}
            section[top][parts[1]] = value

    for name, mapping in section.items():
        if mapping:
            raw.setdefault(name, {})
            for k, v in mapping.items():
                raw[name][k] = _coerce(v)

    return raw


def _coerce(value: str) -> Any:
    """Best-effort type coercion for env strings."""
    try:
        lowered = value.lower()
        if lowered in ("true", "false"):
            return lowered == "true"
        if lowered in ("null", "none"):
            return None
    except AttributeError:
        return value

    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value
