"""Command-line entry point: `etl-pipeline run --source data/raw --dest warehouse.db`."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from etl_pipeline.extract import extract
from etl_pipeline.load import load_to_warehouse, write_quarantine_report
from etl_pipeline.transform import transform
from etl_pipeline.validate import categorize, validate_records


def run_pipeline(source: str, dest: str) -> dict[str, Any]:
    """Run extract -> validate -> transform -> load end to end.

    Returns a summary dict used both for printing and for tests.
    """
    raw_records = extract(source)
    valid_records, quarantined = validate_records(raw_records)
    transformed, duplicates_removed = transform(valid_records)

    dest_path = Path(dest)
    quarantine_path = dest_path.with_name("quarantine.csv")

    rows_loaded = load_to_warehouse(transformed, dest_path)
    write_quarantine_report(quarantined, quarantine_path)

    reason_counts = Counter(categorize(record.reason) for record in quarantined)

    return {
        "rows_extracted": len(raw_records),
        "rows_valid": len(valid_records),
        "duplicates_removed": duplicates_removed,
        "rows_loaded": rows_loaded,
        "rows_quarantined": len(quarantined),
        "reason_counts": reason_counts,
        "dest": str(dest_path),
        "quarantine_path": str(quarantine_path),
    }


def _print_summary(summary: dict[str, Any]) -> None:
    print("ETL Pipeline Summary")
    print("=" * 40)
    print(f"Rows extracted:            {summary['rows_extracted']}")
    print(f"Rows valid:                {summary['rows_valid']}")
    print(f"Duplicate rows merged:     {summary['duplicates_removed']}")
    print(f"Rows loaded to warehouse:  {summary['rows_loaded']}  -> {summary['dest']}")
    quarantine_line = f"Rows quarantined:          {summary['rows_quarantined']}"
    print(f"{quarantine_line}  -> {summary['quarantine_path']}")

    reason_counts: Counter[str] = summary["reason_counts"]
    if reason_counts:
        print()
        print("Quarantine reasons:")
        for reason, count in reason_counts.most_common():
            print(f"  {count:>3}  {reason}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="etl-pipeline", description="Extract, validate, transform, and load order data."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run", help="Run the full pipeline end to end and print a summary."
    )
    run_parser.add_argument(
        "--source",
        default="data/raw",
        help="Directory containing raw .csv/.json source files (default: data/raw)",
    )
    run_parser.add_argument(
        "--dest",
        default="warehouse.db",
        help="Path to the SQLite warehouse database to write (default: warehouse.db)",
    )

    args = parser.parse_args(argv)

    if args.command == "run":
        summary = run_pipeline(args.source, args.dest)
        _print_summary(summary)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
