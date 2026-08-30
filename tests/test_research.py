"""Tests for the research layer (metrics, symbols, factor registry)."""
import pandas as pd
import pytest

from ntquant.research.factors import FACTORY_CONFIGS, build_factor, canonical
from ntquant.research.metrics import METRIC_KEYS, compute_max_drawdown, extract_six
from ntquant.research.symbols import SUPPORTED_SYMBOLS, build_instrument, get_spec


def test_supported_symbols():
    assert SUPPORTED_SYMBOLS == ("BTC", "ETH", "SOL")


def test_symbol_spec_markets():
    spec = get_spec("BTC")
    assert spec.instrument_id("perp").endswith("-PERP.BINANCE")
    assert spec.instrument_id("spot").endswith(".BINANCESPOT")
    assert spec.bar_type("perp") == "BTCUSDT-PERP.BINANCE-15-MINUTE-LAST-EXTERNAL"
    assert spec.bar_type("spot") == "BTCUSDT.BINANCESPOT-15-MINUTE-LAST-EXTERNAL"
    # spot venue name must be hyphen-free for 1.231.0
    assert spec.venue_name("spot") == "BINANCESPOT"
    assert "-" not in spec.venue_name("spot")
    # size precision differs between markets
    assert spec.size_precision("perp") != spec.size_precision("spot")


def test_symbol_spec_raises_unknown():
    with pytest.raises(ValueError, match="Unknown symbol"):
        get_spec("XRP")


def test_build_instrument_spot_is_currency_pair():
    spec = get_spec("ETH")
    inst = build_instrument(spec, "spot")
    assert inst.id.value == "ETHUSDT.BINANCESPOT"
    # CurrencyPair carries instrument_class SPOT
    assert inst.__class__.__name__ == "CurrencyPair"


def test_build_instrument_perp_is_crypto_perpetual():
    spec = get_spec("SOL")
    inst = build_instrument(spec, "perp")
    assert inst.id.value == "SOLUSDT-PERP.BINANCE"
    assert inst.__class__.__name__ == "CryptoPerpetual"
    assert inst.size_precision == 3


def test_compute_max_drawdown():
    equity = pd.Series([100.0, 120.0, 90.0, 110.0, 80.0, 130.0])
    account_df = pd.DataFrame({"total": equity})
    dd = compute_max_drawdown(account_df)
    # peak 120 -> trough 80 = -33.33% -> positive 33.3333
    assert dd == pytest.approx(33.3333, abs=1e-3)


def test_compute_max_drawdown_empty():
    assert compute_max_drawdown(None) is None
    assert compute_max_drawdown(pd.DataFrame()) is None


def test_extract_six_covers_metric_keys():
    # Extract on a real (fast, synthetic) backtest outcome.
    from ntquant.backtest.runner import run_backtest
    from ntquant.config import load_backtest_config

    cfg = load_backtest_config()
    cfg = type(cfg)(
        venue=cfg.venue,
        instrument=cfg.instrument,
        strategy=cfg.strategy,
        data=type(cfg.data)(count=300, seed=42, catalog_path="docs/data"),
        output_path="output",
        log_level="WARNING",
    )
    outcome = run_backtest(cfg)
    six = extract_six(outcome)
    assert set(six.keys()) == set(METRIC_KEYS)
    outcome.engine.dispose()


def test_factors_registered():
    # All five classic factors must be registered.
    for name in ["ema_cross", "rsi_reversal", "bollinger_reversal", "roc_momentum", "macd_cross"]:
        assert name in FACTORY_CONFIGS
        assert name in FACTORY_CONFIGS
        assert name in __import__("ntquant.research.factors", fromlist=["FACTOR_BUILDERS"]).FACTOR_BUILDERS


def test_canonical_resolves_aliases():
    assert canonical("rsi") == "rsi_reversal"
    assert canonical("macd") == "macd_cross"
    assert canonical("emacross") == "ema_cross"
    assert canonical("ema_cross") == "ema_cross"


def test_build_factor_builds_all():
    from ntquant.config import load_backtest_config

    cfg = load_backtest_config()
    for name in ["ema_cross", "rsi_reversal", "bollinger_reversal", "roc_momentum", "macd_cross"]:
        strategy = build_factor(name, cfg)
        assert strategy is not None
        # factor-specific config fields flow through
        cfg_obj = strategy.config
        if name == "rsi_reversal":
            assert cfg_obj.oversold == 30.0
        elif name == "bollinger_reversal":
            assert cfg_obj.num_std == 2.0
        elif name == "roc_momentum":
            assert cfg_obj.entry_threshold == 1.0
        elif name == "macd_cross":
            assert cfg_obj.signal_period == 9
        elif name == "ema_cross":
            assert cfg_obj.fast_period > 0

