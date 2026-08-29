"""Command-line entry point for ntquant.

Subcommands:
- backtest: run a single EMA cross backtest + reports.
- param:    grid-search strategy parameters, print/save results.
- report:   generate CSV reports + HTML tearsheet from a backtest.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from ntquant.config import load_backtest_config, load_param_config


def _env() -> None:
    load_dotenv()


def _cmd_backtest(args: argparse.Namespace) -> int:
    from ntquant.backtest.runner import run_backtest
    from ntquant.analysis.reports import generate_all_reports
    from ntquant.logging import configure_python_logging

    cfg = load_backtest_config(args.config)
    configure_python_logging(cfg.log_level)
    outcome = run_backtest(cfg, use_catalog=args.catalog)
    paths = generate_all_reports(outcome, cfg.output_path, prefix=args.prefix)
    print(f"Backtest complete. PnL(total): {outcome.stats.stats_pnls.get('USD', {}).get('PnL (total)')}")
    for name, path in paths.items():
        print(f"  {name}: {path}")
    outcome.engine.dispose()
    return 0


def _cmd_param(args: argparse.Namespace) -> int:
    from ntquant.backtest.parameters import scan_parameters

    base = load_backtest_config()
    pc = load_param_config(args.config)
    df = scan_parameters(base, pc)
    print(df.to_string())

    out = Path(pc.output_path)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "param_results.csv"
    df.to_csv(dest)
    print(f"\nSaved parameter scan to {dest}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    from ntquant.backtest.runner import run_backtest
    from ntquant.analysis.reports import generate_all_reports
    from ntquant.analysis.visuals import make_tearsheet

    cfg = load_backtest_config(args.config)
    outcome = run_backtest(cfg, use_catalog=True)
    paths = generate_all_reports(outcome, cfg.output_path, prefix="analysis")
    tearsheet = make_tearsheet(outcome, Path(cfg.output_path) / "tearsheet.html")
    for name, path in paths.items():
        print(f"  {name}: {path}")
    print(f"  tearsheet: {tearsheet}")
    outcome.engine.dispose()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ntquant", description="NautilusTrader quant scaffold")
    sub = parser.add_subparsers(dest="command", required=True)

    bt = sub.add_parser("backtest", help="run a single backtest")
    bt.add_argument("--config", default=None, help="path to backtest YAML")
    bt.add_argument("--catalog", action="store_true", help="load bars from catalog")
    bt.add_argument("--prefix", default="run", help="output file prefix")
    bt.set_defaults(func=_cmd_backtest)

    pm = sub.add_parser("param", help="run a parameter scan")
    pm.add_argument("--config", default=None, help="path to param YAML")
    pm.set_defaults(func=_cmd_param)

    rp = sub.add_parser("report", help="generate CSV reports + tearsheet")
    rp.add_argument("--config", default=None, help="path to backtest YAML")
    rp.set_defaults(func=_cmd_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    _env()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
