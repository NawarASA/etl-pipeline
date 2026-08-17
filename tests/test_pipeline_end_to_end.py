"""End-to-end test: run the full pipeline against small fixture files and
assert the right counts land in the warehouse vs quarantine.
"""

from __future__ import annotations

import json
import sqlite3

from etl_pipeline.cli import run_pipeline

CSV_CONTENT = """order_id,customer_email,product_sku,quantity,unit_price,order_date,status
ORD-1,alice@example.com,SKU-1,2,10.00,2026-01-01,completed
ORD-2,not-an-email,SKU-2,1,5.00,2026-01-02,pending
ORD-3,carol@example.com,SKU-3,-1,7.00,2026-01-03,completed
ORD-4,dave@example.com,SKU-4,1,abc,2026-01-04,completed
"""

JSON_CONTENT = [
    {
        "order_id": "ORD-4",
        "customer_email": "dave@example.com",
        "product_sku": "SKU-4",
        "quantity": 1,
        "unit_price": "9.00",
        "order_date": "2026-01-05",
        "status": "completed",
    },
    {
        "order_id": "ORD-5",
        "customer_email": "erin@example.com",
        "product_sku": "",
        "quantity": 2,
        "unit_price": "3.00",
        "order_date": "2026-01-06",
        "status": "pending",
    },
    {
        "order_id": "ORD-6",
        "customer_email": "frank@example.com",
        "product_sku": "SKU-6",
        "quantity": 3,
        "unit_price": "4.50",
        "order_date": "2026-01-07",
        "status": "shipped",
    },
]


def _write_fixtures(tmp_path):
    source_dir = tmp_path / "raw"
    source_dir.mkdir()
    (source_dir / "orders.csv").write_text(CSV_CONTENT, encoding="utf-8")
    (source_dir / "orders.json").write_text(json.dumps(JSON_CONTENT), encoding="utf-8")
    return source_dir


def test_end_to_end_pipeline_counts(tmp_path):
    source_dir = _write_fixtures(tmp_path)
    dest_db = tmp_path / "warehouse.db"

    summary = run_pipeline(str(source_dir), str(dest_db))

    # 4 CSV rows + 3 JSON rows = 7 raw records extracted.
    assert summary["rows_extracted"] == 7
    # Invalid: ORD-2 (bad email), ORD-3 (negative qty), ORD-4-csv (bad price),
    # ORD-5 (missing sku) = 4 quarantined.
    assert summary["rows_quarantined"] == 4
    # Valid: ORD-1, ORD-4-json, ORD-6 = 3 (ORD-4 appears once, valid, from JSON).
    assert summary["rows_valid"] == 3
    assert summary["duplicates_removed"] == 0
    assert summary["rows_loaded"] == 3

    # The warehouse actually has 3 rows.
    conn = sqlite3.connect(dest_db)
    try:
        rows = conn.execute("SELECT order_id, line_total FROM orders ORDER BY order_id").fetchall()
    finally:
        conn.close()
    assert [r[0] for r in rows] == ["ORD-1", "ORD-4", "ORD-6"]
    assert rows[0][1] == 20.0  # ORD-1: qty 2 * 10.00

    # The quarantine report exists and has a header + 4 data rows.
    quarantine_path = tmp_path / "quarantine.csv"
    lines = quarantine_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 5  # header + 4 rows

    reasons = " ".join(lines[1:])
    assert "invalid email format" in reasons
    assert "quantity must be a positive integer" in reasons
    assert "unit_price is not a valid number" in reasons
    assert "missing required field: product_sku" in reasons


def test_end_to_end_pipeline_dedupes_duplicate_order_id(tmp_path):
    source_dir = _write_fixtures(tmp_path)
    dest_db = tmp_path / "warehouse.db"

    summary = run_pipeline(str(source_dir), str(dest_db))

    # ORD-4 appears once valid (CSV copy is quarantined for bad price), so
    # no duplicate merge happens here -- covered by test_transform.py's
    # dedicated dedupe tests. This test just confirms the loaded rows are
    # unique by order_id even when the source had a repeated id.
    conn = sqlite3.connect(dest_db)
    try:
        (count,) = conn.execute("SELECT COUNT(DISTINCT order_id) FROM orders").fetchone()
        (total,) = conn.execute("SELECT COUNT(*) FROM orders").fetchone()
    finally:
        conn.close()
    assert count == total == summary["rows_loaded"]
