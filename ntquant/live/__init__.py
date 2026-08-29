"""Live trading placeholder (phase 2).

Not implemented in this scaffold. When extending to live, wire a ``LiveNode``
with an adapter (e.g. Binance/Bybit) using the same strategy classes — the
strategy source is engine-agnostic and reuses ``ntquant.strategies``.

Key references (verify imports against 1.231.0 first):
- ``nautilus_trader.live.node: LiveNode``
- ``nautilus_trader.live.node_builder: LiveNodeBuilder`` (or ``LiveNode.builder``)
- ``nautilus_trader.config: LiveNodeConfig``
"""
from __future__ import annotations


class LiveScaffold:
    """Placeholder for a live node setup.

    See :func:`configure_live` for the intended wiring; implementing live
    trading is intentionally deferred to the next phase.
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "Live trading is deferred to phase 2. See ntquant/live/__init__.py."
        )


def configure_live() -> None:
    """Documented stub describing the live wiring (not implemented)."""
    raise NotImplementedError("configure_live is a placeholder for phase 2.")
