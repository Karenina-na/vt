"""Tests for strategy configuration and risk helpers."""
from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId

from ntquant.risk import position_size_from_risk
from ntquant.strategies.ema_cross import EMACrossConfig, EMACrossStrategy


def test_ema_config_is_constructible():
    cfg = EMACrossConfig(
        instrument_id=InstrumentId.from_str("EUR/USD.SIM"),
        bar_type=BarType.from_str("EUR/USD.SIM-1-MINUTE-LAST-EXTERNAL"),
        trade_size="10000",
        fast_period=10,
        slow_period=30,
        strategy_id="EMA-001",
    )
    assert cfg.fast_period == 10
    assert cfg.slow_period == 30


def test_ema_strategy_instantiates():
    cfg = EMACrossConfig(
        instrument_id=InstrumentId.from_str("EUR/USD.SIM"),
        bar_type=BarType.from_str("EUR/USD.SIM-1-MINUTE-LAST-EXTERNAL"),
        trade_size="10000",
        strategy_id="EMA-001",
    )
    strat = EMACrossStrategy(cfg)
    assert strat.config.trade_size == "10000"


def test_position_size_from_risk():
    # 1% of 100k = 1000 risk; stop distance 0.005 -> 200_000 units
    size = position_size_from_risk(100000, "1.0850", "1.0800", "0.01")
    assert float(size) == 200000.00
