"""Tests for config loading and parameter scanning helpers."""
import ntquant.config as c
from ntquant.config import load_backtest_config
from ntquant.backtest.parameters import _grid, _build_config

_SIM_EXAMPLE = """\
venue:
  name: SIM
  oms_type: NETTING
  strategy:
    name: ema_cross
    fast_period: 10
    slow_period: 30
"""


def _isolated(monkeypatch, tmp_path, example: str = _SIM_EXAMPLE, user: str | None = None):
    """Point config resolution at a temp dir, optionally with a user copy."""
    (tmp_path / "backtest.example.yaml").write_text(example)
    if user is not None:
        (tmp_path / "backtest.yaml").write_text(user)
    monkeypatch.setattr(c, "_DEFAULT_CONFIG_DIR", tmp_path)


def test_load_backtest_config_defaults(tmp_path, monkeypatch):
    _isolated(monkeypatch, tmp_path)
    cfg = load_backtest_config()
    assert cfg.venue.name == "SIM"
    assert cfg.venue.oms_type == "NETTING"
    assert cfg.strategy.name == "ema_cross"
    assert cfg.strategy.fast_period == 10


def test_defaults_fall_back_via_dataclass(tmp_path, monkeypatch):
    # With no user YAML copy, config derives defaults from the dataclasses (and
    # the .example template when present) rather than a separate defaults dict.
    _isolated(monkeypatch, tmp_path)
    cfg = load_backtest_config()
    assert cfg.venue.name == "SIM"
    assert cfg.data.source == "synthetic"


def test_user_copy_takes_precedence_over_example(tmp_path, monkeypatch):
    # configs/<name>.yaml (user copy) must beat configs/<name>.example.yaml.
    _isolated(
        monkeypatch, tmp_path,
        example="strategy:\n  name: ema_cross\n  fast_period: 10\n",
        user="strategy:\n  name: ema_cross\n  fast_period: 99\n",
    )
    cfg = load_backtest_config()
    assert cfg.strategy.fast_period == 99
    # A field absent from the user copy falls back to the dataclass default.
    assert cfg.venue.name == "SIM"


def test_grid_cartesian_product():
    grid = _grid({"fast_period": [5, 10], "slow_period": [30, 50]})
    assert len(grid) == 4
    assert {"fast_period": 5, "slow_period": 30} in grid


def test_build_config_overrides_and_preserves_data(tmp_path, monkeypatch):
    _isolated(monkeypatch, tmp_path)
    base = load_backtest_config()
    new = _build_config(base, {"fast_period": 15, "slow_period": 40, "trade_size": "20000"})
    assert new.strategy.fast_period == 15
    assert new.strategy.slow_period == 40
    assert new.strategy.trade_size == "20000"
    # data section (source/tz/columns/timestamp_col) must be preserved.
    assert new.data.source == base.data.source
    assert new.data.tz == base.data.tz
    assert new.data.columns == base.data.columns
    assert new.data.timestamp_col == base.data.timestamp_col
    assert new.data.catalog_path == base.data.catalog_path
