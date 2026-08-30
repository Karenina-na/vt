"""Command-line entry point for ntquant.

Subcommands:
- backtest: run a single EMA cross backtest + reports.
- param:    grid-search strategy parameters, print/save results.
- report:   generate CSV reports + HTML tearsheet from a backtest.
- ingest:   fetch external OHLCV data into the catalog.
- research: evaluate a factor across symbols and a time window (six metrics).
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


def _cmd_ingest(args: argparse.Namespace) -> int:
    from ntquant.config import load_backtest_config
    from ntquant.data.ingest import ingest

    cfg = load_backtest_config(args.config)
    outcome = ingest(
        cfg,
        source_name=args.source,
        start=args.start,
        end=args.end,
        limit_total=args.limit,
        overwrite=args.overwrite,
    )
    print(outcome.summary())
    return 0


def _cmd_research(args: argparse.Namespace) -> int:
    from ntquant.config import load_backtest_config
    from ntquant.research.factors import SUPPORTED_FACTORS
    from ntquant.research.runner import run_factor_evaluation
    from ntquant.research.symbols import SUPPORTED_SYMBOLS

    if args.strategy not in SUPPORTED_FACTORS:
        print(f"Unknown factor '{args.strategy}'. Registered: {sorted(SUPPORTED_FACTORS)}")
        return 1

    symbols = args.symbols.split(",") if args.symbols else list(SUPPORTED_SYMBOLS)
    cfg = load_backtest_config(args.config)
    result = run_factor_evaluation(
        factor=args.strategy,
        symbols=symbols,
        base=cfg,
        market=args.market,
        start=args.start,
        end=args.end,
    )
    print(result.frame.to_string(index=False))

    out = Path(cfg.output_path)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / f"research_{args.strategy}_{args.market}.csv"
    result.to_csv(str(dest))
    print(f"\nSaved research table to {dest}")
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

    ing = sub.add_parser("ingest", help="fetch external OHLCV data into the catalog")
    ing.add_argument("--config", default=None, help="path to backtest YAML")
    ing.add_argument("--source", default=None,
                     help="override data.source (csv/parquet/binance/polygon/... )")
    ing.add_argument("--start", default=None,
                     help="window start (ISO datetime or ms epoch), paged fetch")
    ing.add_argument("--end", default=None,
                     help="window end (ISO datetime or ms epoch), paged fetch")
    ing.add_argument("--limit", type=int, default=None,
                     help="total bars to fetch (paged) when no --end window")
    ing.add_argument("--overwrite", action="store_true",
                     help="delete existing bars for this symbol before writing")
    ing.set_defaults(func=_cmd_ingest)

    rs = sub.add_parser("research", help="evaluate a factor across symbols/time window")
    rs.add_argument("--config", default=None, help="path to backtest YAML")
    rs.add_argument("--strategy", default="ema_cross", help="factor/strategy name")
    rs.add_argument("--symbols", default=None, help="comma-separated symbols (default: all)")
    rs.add_argument("--market", default="perp", choices=["perp", "spot"],
                    help="data market (perp default; spot covers pre-2020)")
    rs.add_argument("--start", default=None, help="window start (ISO datetime)")
    rs.add_argument("--end", default=None, help="window end (ISO datetime)")
    rs.set_defaults(func=_cmd_research)

    return parser


def main(argv: list[str] | None = None) -> int:
    _env()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
