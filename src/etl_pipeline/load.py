"""Load transformed records into a local SQLite warehouse, and write the
quarantined rows out as a CSV report with reasons.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from etl_pipeline.transform import TransformedOrder
from etl_pipeline.validate import QuarantinedRecord

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    customer_email TEXT NOT NULL,
    product_sku TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    order_date TEXT NOT NULL,
    status TEXT NOT NULL,
    line_total REAL NOT NULL
)
"""

_UPSERT_SQL = """
INSERT INTO orders
    (order_id, customer_email, product_sku, quantity, unit_price, order_date, status, line_total)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(order_id) DO UPDATE SET
    customer_email = excluded.customer_email,
    product_sku = excluded.product_sku,
    quantity = excluded.quantity,
    unit_price = excluded.unit_price,
    order_date = excluded.order_date,
    status = excluded.status,
    line_total = excluded.line_total
"""


def load_to_warehouse(records: list[TransformedOrder], dest: str | Path) -> int:
    """Create the orders table if needed and upsert every record.

    Returns the number of records loaded.
    """
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(dest_path)
    try:
        connection.execute(CREATE_TABLE_SQL)
        connection.executemany(
            _UPSERT_SQL,
            [
                (
                    r.order_id,
                    r.customer_email,
                    r.product_sku,
                    r.quantity,
                    r.unit_price,
                    r.order_date.isoformat(),
                    r.status,
                    r.line_total,
                )
                for r in records
            ],
        )
        connection.commit()
    finally:
        connection.close()
    return len(records)


def write_quarantine_report(quarantined: list[QuarantinedRecord], dest: str | Path) -> int:
    """Write quarantined rows to a CSV report with reasons.

    Returns the number of rows written.
    """
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    with dest_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["source_file", "source_row", "order_id", "reason", "raw_record"])
        for record in quarantined:
            raw_clean = {
                key: value
                for key, value in record.raw.items()
                if key not in ("source_file", "source_row")
            }
            writer.writerow(
                [
                    record.source_file,
                    record.source_row,
                    record.order_id,
                    record.reason,
                    json.dumps(raw_clean),
                ]
            )
    return len(quarantined)
