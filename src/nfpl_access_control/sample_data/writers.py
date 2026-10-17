"""Output writers and disposable-target safeguards.

The generator only ever writes flat data files (JSON / CSV / NDJSON). It never
touches a database. The safeguards here protect the *output directory* so a
regeneration cannot silently clobber an unrelated folder, and they stamp every
dataset with a manifest marking it fictional and disposable so downstream
import tooling (Codex) can refuse to load it into a non-disposable database.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Iterator
from pathlib import Path

from nfpl_access_control.sample_data import reference as ref

# Written at the root of every output directory. Its presence marks the folder
# as owned by this generator and therefore safe to overwrite on regeneration.
MARKER_NAME = ".nfpl-sample-data"
MARKER_CONTENT = "NFPL deterministic fictional sample data. Disposable. Safe to delete.\n"


class OutputSafetyError(RuntimeError):
    """Raised when writing would touch a directory not owned by the generator."""


def _json_default(value: object) -> str:
    raise TypeError(f"non-serializable value in sample data: {value!r}")


def _dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=_json_default)


def prepare_output_dir(output_dir: Path, *, force: bool) -> None:
    """Create or validate the output directory.

    A directory is writable when it does not exist, is empty, or already carries
    this generator's marker file. Any other existing directory is refused unless
    ``force`` is set, so regeneration cannot overwrite an unrelated folder.
    """

    if output_dir.exists():
        if not output_dir.is_dir():
            raise OutputSafetyError(f"{output_dir} exists and is not a directory")
        entries = [p for p in output_dir.iterdir() if p.name != MARKER_NAME]
        owned = (output_dir / MARKER_NAME).exists()
        if entries and not owned and not force:
            raise OutputSafetyError(
                f"refusing to write into non-empty, unmarked directory {output_dir}; "
                "choose an empty directory or pass force=True"
            )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / MARKER_NAME).write_text(MARKER_CONTENT, encoding="utf-8")


def _csv_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return _dumps(value)
    return str(value)


def write_tables(tables: dict[str, list[dict]], output_dir: Path, *, fmt: str) -> list[str]:
    """Write every table as ``<table>.<ext>``; returns the file names written."""

    written: list[str] = []
    for table, rows in tables.items():
        columns = ref.TABLE_COLUMNS.get(table) or tuple(rows[0].keys()) if rows else ()
        if fmt == "json":
            path = output_dir / f"{table}.json"
            ordered = [{col: row.get(col) for col in columns} for row in rows]
            path.write_text(
                json.dumps(
                    ordered, ensure_ascii=False, indent=2, sort_keys=False, default=_json_default
                )
                + "\n",
                encoding="utf-8",
            )
        elif fmt == "csv":
            path = output_dir / f"{table}.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(columns)
                for row in rows:
                    writer.writerow([_csv_cell(row.get(col)) for col in columns])
        else:
            raise ValueError(f"unknown format {fmt!r}")
        written.append(path.name)
    return written


def write_table_stream(table: str, rows: Iterable[dict], output_dir: Path, *, fmt: str) -> int:
    """Stream rows for one table to disk without materializing them all.

    Returns the number of rows written. Used by benchmark mode to keep memory
    flat regardless of job count.
    """

    columns = ref.TABLE_COLUMNS.get(table)
    count = 0
    if fmt == "ndjson":
        path = output_dir / f"{table}.ndjson"
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                payload = {col: row.get(col) for col in columns} if columns else row
                handle.write(_dumps(payload) + "\n")
                count += 1
    elif fmt == "csv":
        path = output_dir / f"{table}.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            iterator: Iterator[dict] = iter(rows)
            first = next(iterator, None)
            effective_cols = columns or (tuple(first.keys()) if first else ())
            writer.writerow(effective_cols)
            for row in [first] if first is not None else []:
                writer.writerow([_csv_cell(row.get(col)) for col in effective_cols])
                count += 1
            for row in iterator:
                writer.writerow([_csv_cell(row.get(col)) for col in effective_cols])
                count += 1
    else:
        raise ValueError(f"unknown stream format {fmt!r}")
    return count


def write_manifest(
    output_dir: Path,
    *,
    mode: str,
    fmt: str,
    counts: dict[str, int],
    edge_cases: list[str],
    extra: dict | None = None,
) -> None:
    manifest = {
        "dataset": "nfpl-access-control-sample-data",
        "mode": mode,
        "format": fmt,
        "environment": "disposable-sample-data",
        "fictional": True,
        "load_warning": (
            "Fictional test data. Load only into a disposable/non-production "
            "database that has NFPL migrations applied (system roles installed)."
        ),
        "generated_at_note": "All timestamps are derived from a fixed epoch.",
        "produced_at": "2025-01-06T09:00:00+00:00",
        "row_counts": counts,
        "edge_cases": edge_cases,
    }
    if extra:
        manifest.update(extra)
    (output_dir / "_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
