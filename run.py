"""ntquant entry point.

Usage:
    python run.py backtest
    python run.py param
    python run.py report
    python run.py ingest
"""
import sys

from ntquant.cli import main

if __name__ == "__main__":
    sys.exit(main())
