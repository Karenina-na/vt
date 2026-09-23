"""End-to-end backtest test (fast: small bar count)."""
from dataclasses import replace

from ntquant.backtest.runner import run_backtest
from ntquant.cli import main
from ntquant.config import load_backtest_config


def test_run_backtest_produces_reports():
    cfg = load_backtest_config("configs/backtest.example.yaml")
    # Small dataset for CI speed
    cfg = type(cfg)(
        venue=cfg.venue,
        instrument=cfg.instrument,
        strategy=cfg.strategy,
        data=type(cfg.data)(count=300, seed=42, catalog_path="docs/data"),
        output_path="output",
        log_level="WARNING",
    )
    outcome = run_backtest(cfg)
    assert len(outcome.orders_df) >= 1
    assert outcome.engine.cache.orders()
    outcome.engine.dispose()


def test_non_ema_strategy_runs_with_own_parameters(tmp_path):
    cfg = load_backtest_config("configs/backtest.example.yaml")
    cfg = replace(
        cfg,
        strategy=replace(cfg.strategy, name="rsi_reversal", params={}),
        data=replace(cfg.data, count=300, seed=42),
        output_path=str(tmp_path),
        log_level="WARNING",
    )
    outcome = run_backtest(cfg, strategy_params={"period": 7, "oversold": 35})
    try:
        assert outcome.engine.cache.orders()
    finally:
        outcome.engine.dispose()


def test_backtest_cli_accepts_strategy_and_params(tmp_path):
    config = tmp_path / "backtest.yaml"
    config.write_text(
        "data:\n  count: 300\n  seed: 42\noutput_path: " + str(tmp_path) + "\n",
        encoding="utf-8",
    )
    assert main([
        "backtest", "--config", str(config), "--strategy", "rsi_reversal",
        "--param", "period=7,oversold=35",
    ]) == 0
    assert (tmp_path / "run_orders.csv").exists()


def test_backtest_cli_uses_strategy_from_yaml(tmp_path):
    config = tmp_path / "backtest.yaml"
    config.write_text(
        f"strategy:\n  name: rsi_reversal\n  period: 7\n"
        f"data:\n  count: 300\n  seed: 42\n"
        f"output_path: {tmp_path}\nlog_level: WARNING\n",
        encoding="utf-8",
    )
    assert main(["backtest", "--config", str(config)]) == 0
    assert (tmp_path / "run_orders.csv").exists()
