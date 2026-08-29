"""End-to-end backtest test (fast: small bar count)."""
from ntquant.config import load_backtest_config
from ntquant.backtest.runner import run_backtest


def test_run_backtest_produces_reports():
    cfg = load_backtest_config()
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
