"""Tests for config loading and parameter scanning helpers."""
from ntquant.config import load_backtest_config
from ntquant.backtest.parameters import _grid, _build_config


def test_load_backtest_config_defaults():
    cfg = load_backtest_config()
    assert cfg.venue.name == "SIM"
    assert cfg.venue.oms_type == "NETTING"
    assert cfg.strategy.name == "ema_cross"
    assert cfg.strategy.fast_period == 10


def test_grid_cartesian_product():
    grid = _grid({"fast_period": [5, 10], "slow_period": [30, 50]})
    assert len(grid) == 4
    assert {"fast_period": 5, "slow_period": 30} in grid


def test_build_config_overrides():
    base = load_backtest_config()
    new = _build_config(base, {"fast_period": 15, "slow_period": 40, "trade_size": "20000"})
    assert new.strategy.fast_period == 15
    assert new.strategy.slow_period == 40
    assert new.strategy.trade_size == "20000"
