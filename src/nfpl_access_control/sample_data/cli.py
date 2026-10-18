"""Command-line entry point for NFPL sample generation and disposable seeding.

Two modes, both deterministic and idempotent:

* ``standard``  -> rich 5/10/20/300-500 dataset with full edge cases (JSON/CSV)
* ``benchmark`` -> streamed 500-employee / 200,000-job dataset (NDJSON/CSV)

Generation writes flat files. Database imports use separate, explicit commands
for disposable SQLite and PostgreSQL targets.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from alembic.config import Config

from alembic import command
from nfpl_access_control.core.config import normalize_database_url
from nfpl_access_control.db.session import create_database_engine
from nfpl_access_control.sample_data.benchmark import (
    BENCHMARK_STREAMS,
    BenchmarkConfig,
    expected_counts,
)
from nfpl_access_control.sample_data.builder import DatasetBuilder, DatasetConfig
from nfpl_access_control.sample_data.importer import SampleImportError, import_dataset
from nfpl_access_control.sample_data.writers import (
    prepare_output_dir,
    write_manifest,
    write_table_stream,
    write_tables,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nfpl-sample-data",
        description="Generate deterministic fictional NFPL sample datasets.",
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    standard = sub.add_parser("standard", help="rich dataset with full edge cases")
    standard.add_argument("--out", type=Path, required=True, help="output directory")
    standard.add_argument("--format", choices=("json", "csv"), default="json")
    standard.add_argument("--jobs", type=int, default=420, help="300-500 shipments")
    standard.add_argument("--branches", type=int, default=5)
    standard.add_argument("--clients", type=int, default=10)
    standard.add_argument("--employees", type=int, default=20)
    standard.add_argument(
        "--force", action="store_true", help="overwrite a non-empty, unmarked output directory"
    )

    bench = sub.add_parser("benchmark", help="large streamed benchmark dataset")
    bench.add_argument("--out", type=Path, required=True, help="output directory")
    bench.add_argument("--format", choices=("ndjson", "csv"), default="ndjson")
    bench.add_argument("--jobs", type=int, default=200_000)
    bench.add_argument("--employees", type=int, default=500)
    bench.add_argument("--branches", type=int, default=10)
    bench.add_argument("--clients", type=int, default=200)
    bench.add_argument("--force", action="store_true")

    seed = sub.add_parser(
        "seed-demo",
        help="migrate and seed an empty disposable SQLite database",
    )
    seed.add_argument("--database-url", required=True)
    seed.add_argument(
        "--confirm-disposable",
        action="store_true",
        help="confirm that the target is disposable and contains no data to preserve",
    )

    postgres_seed = sub.add_parser(
        "seed-postgres",
        help="seed an empty, migrated, explicitly disposable PostgreSQL database",
    )
    postgres_seed.add_argument(
        "--confirm-disposable-postgres",
        action="store_true",
        help="confirm that DATABASE_URL targets disposable PostgreSQL with no data to preserve",
    )
    return parser


def _run_standard(args: argparse.Namespace) -> None:
    config = DatasetConfig(
        branches=args.branches, clients=args.clients, employees=args.employees, jobs=args.jobs
    )
    dataset = DatasetBuilder(config).build()
    prepare_output_dir(args.out, force=args.force)
    write_tables(dataset.tables, args.out, fmt=args.format)
    counts = {table: len(rows) for table, rows in dataset.tables.items()}
    write_manifest(
        args.out, mode="standard", fmt=args.format, counts=counts, edge_cases=dataset.edge_cases
    )
    print(
        f"Wrote {sum(counts.values())} rows across {len(counts)} tables "
        f"({args.format}) to {args.out}"
    )


def _run_benchmark(args: argparse.Namespace) -> None:
    config = BenchmarkConfig(
        branches=args.branches, clients=args.clients, employees=args.employees, jobs=args.jobs
    )
    prepare_output_dir(args.out, force=args.force)
    counts: dict[str, int] = {}
    for table, stream in BENCHMARK_STREAMS.items():
        counts[table] = write_table_stream(table, stream(config), args.out, fmt=args.format)
    write_manifest(
        args.out,
        mode="benchmark",
        fmt=args.format,
        counts=counts,
        edge_cases=["streamed minimal-history benchmark"],
        extra={"expected_counts": expected_counts(config)},
    )
    print(
        f"Wrote {sum(counts.values())} rows across {len(counts)} tables "
        f"({args.format}) to {args.out}"
    )


def _run_seed(args: argparse.Namespace) -> None:
    database_url = args.database_url.strip()
    if not args.confirm_disposable:
        raise SampleImportError("seed-demo requires --confirm-disposable.")
    if not database_url.startswith("sqlite:///") or ":memory:" in database_url:
        raise SampleImportError("seed-demo accepts a file-backed SQLite URL only.")
    database_path = Path(database_url.removeprefix("sqlite:///")).resolve()
    if database_path.name.lower() == "nfpl.db":
        raise SampleImportError("Refusing to seed the default application database nfpl.db.")
    password = os.getenv("NFPL_DEMO_PASSWORD")
    if password is None:
        raise SampleImportError("Set NFPL_DEMO_PASSWORD through the process environment.")

    alembic_config = Config("alembic.ini")
    alembic_config.attributes["database_url"] = database_url
    command.upgrade(alembic_config, "head")
    engine = create_database_engine(database_url)
    try:
        result = import_dataset(engine, DatasetBuilder().build(), demo_password=password)
    finally:
        engine.dispose()
    print(
        f"Seeded {result.total_rows} rows into disposable SQLite database "
        f"{database_path.name}; plaintext credentials were not stored or printed."
    )


def _run_postgres_seed(args: argparse.Namespace) -> None:
    if not args.confirm_disposable_postgres:
        raise SampleImportError("seed-postgres requires --confirm-disposable-postgres.")
    raw_database_url = os.getenv("DATABASE_URL")
    if raw_database_url is None or not raw_database_url.strip():
        raise SampleImportError("Set DATABASE_URL through the process environment.")
    database_url = normalize_database_url(raw_database_url.strip())
    if not database_url.startswith("postgresql+psycopg://"):
        raise SampleImportError("seed-postgres accepts a PostgreSQL DATABASE_URL only.")
    password = os.getenv("NFPL_DEMO_PASSWORD")
    if password is None:
        raise SampleImportError("Set NFPL_DEMO_PASSWORD through the process environment.")

    engine = create_database_engine(database_url)
    try:
        result = import_dataset(engine, DatasetBuilder().build(), demo_password=password)
    finally:
        engine.dispose()
    print(
        f"Seeded {result.total_rows} rows into confirmed disposable PostgreSQL; "
        "the database URL and plaintext credentials were not printed."
    )


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    if args.mode == "standard":
        _run_standard(args)
    elif args.mode == "benchmark":
        _run_benchmark(args)
    elif args.mode == "seed-postgres":
        _run_postgres_seed(args)
    else:
        _run_seed(args)


if __name__ == "__main__":
    main()
