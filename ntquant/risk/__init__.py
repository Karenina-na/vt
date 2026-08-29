"""Risk management utilities (pre-trade sizing + engine config)."""
from __future__ import annotations

from decimal import Decimal

from nautilus_trader.config import RiskEngineConfig


def position_size_from_risk(
    account_balance: Decimal | str,
    entry_price: Decimal | str,
    stop_price: Decimal | str,
    risk_per_trade: Decimal | str,
) -> Decimal:
    """Compute a position quantity from account risk.

    Size = risk_per_trade / (|entry - stop|). Returns the notional quantity of
    the trading unit (before instrument size precision normalization).

    Args:
        account_balance: Account equity, or a numeric string.
        entry_price: Expected entry price, or a numeric string.
        stop_price: Stop price level, or a numeric string.
        risk_per_trade: Fraction of the account to risk (e.g. ``0.01`` = 1%).
    """
    balance = account_balance if isinstance(account_balance, Decimal) else Decimal(str(account_balance))
    entry = entry_price if isinstance(entry_price, Decimal) else Decimal(str(entry_price))
    stop = stop_price if isinstance(stop_price, Decimal) else Decimal(str(stop_price))
    risk = risk_per_trade if isinstance(risk_per_trade, Decimal) else Decimal(str(risk_per_trade))

    risk_amount = balance * risk
    per_unit = abs(entry - stop)
    if per_unit == 0:
        return Decimal("0")
    return (risk_amount / per_unit).quantize(Decimal("0.01"))


def build_risk_engine_config(
    max_order_submit_rate: int = 0,
    max_order_modify_rate: int = 0,
    max_notional_per_order: str | None = None,
    bypass: bool = True,
):
    """Build a RiskEngineConfig with optional rate/notional limits.

    Warning (1.231.0): with ``bypass=False`` the engine's RiskEngine raises
    ``AttributeError: 'int' object has no attribute 'split'`` for
    ``max_notional_per_order``. The built-in ``bypass=True`` is therefore the
    safe default. Keep it ``True`` unless this is resolved in a newer version.

    ``max_order_submit_rate``/``max_order_modify_rate`` of ``0`` means unlimited.
    """
    return RiskEngineConfig(
        bypass=bypass,
        max_order_submit_rate=max_order_submit_rate,
        max_order_modify_rate=max_order_modify_rate,
        max_notional_per_order=max_notional_per_order,
    )
