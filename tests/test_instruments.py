"""Tests for asset-class aware instrument construction."""
import ntquant.config as C
from ntquant.backtest.instruments import make_instrument
from ntquant.config import BacktestConfig, InstrumentConfig


def _wrapped(instrument: InstrumentConfig) -> BacktestConfig:
    return BacktestConfig(instrument=instrument)


def test_fx_instrument():
    cfg = _wrapped(InstrumentConfig(asset_class="FX"))
    inst = make_instrument(cfg)
    assert inst.__class__.__name__ == "CurrencyPair"
    assert inst.id.value == "EUR/USD.SIM"


def test_equity_instrument():
    cfg = _wrapped(
        InstrumentConfig(
            asset_class="EQUITY",
            instrument_id="AAPL.SIM",
            raw_symbol="AAPL",
            base_currency="USD",
            price_precision=2,
            price_increment="0.01",
        )
    )
    inst = make_instrument(cfg)
    assert inst.__class__.__name__ == "Equity"
    assert inst.id.value == "AAPL.SIM"


def test_crypto_instrument():
    cfg = _wrapped(
        InstrumentConfig(
            asset_class="CRYPTOCURRENCY",
            instrument_id="BTCUSDT-PERP.SIM",
            raw_symbol="BTCUSDT-PERP",
            base_currency="BTC",
            quote_currency="USDT",
            settlement_currency="USDT",
            price_precision=2,
            size_precision=0,
            price_increment="0.01",
            size_increment="1",
        )
    )
    inst = make_instrument(cfg)
    assert inst.__class__.__name__ == "CryptoPerpetual"
    assert inst.quote_currency.code == "USDT"
