"""Extract raw records from CSV and JSON source files into a common,
un-validated intermediate format: a flat list of dicts, one per source row,
each tagged with where it came from for traceability into the quarantine
report.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def _read_csv(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        # Row 1 is the header, so the first data row is row 2.
        for line_number, row in enumerate(reader, start=2):
            record = dict(row)
            record["source_file"] = path.name
            record["source_row"] = line_number
            records.append(record)
    return records


def _read_json(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    records: list[dict[str, Any]] = []
    for index, row in enumerate(data, start=1):
        record = dict(row)
        record["source_file"] = path.name
        record["source_row"] = index
        records.append(record)
    return records


def extract(source_dir: str | Path) -> list[dict[str, Any]]:
    """Read every ``*.csv`` and ``*.json`` file directly inside ``source_dir``
    into a single flat list of raw record dicts.

    Files are read in sorted order within each format (CSV first, then
    JSON) so pipeline runs are deterministic.
    """
    source_path = Path(source_dir)
    if not source_path.is_dir():
        raise FileNotFoundError(f"source directory not found: {source_path}")

    records: list[dict[str, Any]] = []
    for csv_path in sorted(source_path.glob("*.csv")):
        records.extend(_read_csv(csv_path))
    for json_path in sorted(source_path.glob("*.json")):
        records.extend(_read_json(json_path))
    return records
