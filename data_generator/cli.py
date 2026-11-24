"""Command-line interface.

python -m data_generator seed  [--seed N] [--anchor-date YYYY-MM-DD]
python -m data_generator stats
"""

from __future__ import annotations

import argparse
import logging
from datetime import date

from data_generator import db, seed
from data_generator.config import GeneratorConfig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="data_generator", description="Synthetic source data for Cedar & Co."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    seed_parser = commands.add_parser(
        "seed", help="rebuild the historical data (deletes existing rows)"
    )
    seed_parser.add_argument("--seed", type=int, help="random seed (default: GENERATOR_SEED or 42)")
    seed_parser.add_argument(
        "--anchor-date",
        type=date.fromisoformat,
        help="last day of the history, YYYY-MM-DD (default: GENERATOR_ANCHOR_DATE)",
    )
    commands.add_parser("stats", help="show row counts per table")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"
    )

    if args.command == "seed":
        seed.run(GeneratorConfig.from_env(seed=args.seed, anchor_date=args.anchor_date))
    elif args.command == "stats":
        _print_stats()
    return 0


def _print_stats() -> None:
    for dbname in db.SOURCE_DATABASES:
        print(f"\n{dbname}")
        for table, count in db.table_counts(dbname):
            print(f"  {table:<24} {count:>12,}")
