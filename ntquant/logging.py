"""Unified logging configuration for ntquant."""
from __future__ import annotations

import logging
import sys

from nautilus_trader.config import LoggingConfig


def get_logging_config(level: str = "INFO") -> LoggingConfig:
    """Build a NautilusTrader LoggingConfig at the given level."""
    return LoggingConfig(log_level=level.upper())


def configure_python_logging(level: str = "INFO") -> None:
    """Configure the Python standard logger to mirror ntquant's level."""
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
