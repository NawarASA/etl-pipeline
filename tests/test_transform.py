"""Tests for dedup logic and the computed line_total transform."""

from __future__ import annotations

from datetime import date

from etl_pipeline.schema import OrderRecord
from etl_pipeline.transform import dedupe, transform


def _record(**overrides):
    base = {
        "order_id": "ORD-1",
        "customer_email": "a@example.com",
        "product_sku": "SKU-1",
        "quantity": 2,
        "unit_price": 10.0,
        "order_date": date(2026, 1, 1),
        "status": "completed",
    }
    base.update(overrides)
    return OrderRecord(**base)


def test_line_total_is_quantity_times_unit_price():
    records = [_record(quantity=3, unit_price=12.5)]
    transformed, _ = transform(records)
    assert transformed[0].line_total == 37.5


def test_dedupe_keeps_only_one_record_per_order_id():
    records = [_record(order_id="ORD-1"), _record(order_id="ORD-1"), _record(order_id="ORD-2")]
    deduped, duplicates_removed = dedupe(records)
    ids = sorted(r.order_id for r in deduped)
    assert ids == ["ORD-1", "ORD-2"]
    assert duplicates_removed == 1


def test_dedupe_keeps_most_recent_by_order_date():
    older = _record(order_id="ORD-1", order_date=date(2026, 1, 1), status="pending")
    newer = _record(order_id="ORD-1", order_date=date(2026, 1, 5), status="shipped")
    deduped, _ = dedupe([older, newer])
    assert len(deduped) == 1
    assert deduped[0].status == "shipped"
    assert deduped[0].order_date == date(2026, 1, 5)


def test_dedupe_breaks_date_tie_with_completeness():
    same_date = date(2026, 1, 1)
    less_complete = _record(order_id="ORD-1", order_date=same_date, status="unknown")
    more_complete = _record(order_id="ORD-1", order_date=same_date, status="completed")
    deduped, _ = dedupe([less_complete, more_complete])
    assert len(deduped) == 1
    assert deduped[0].status == "completed"


def test_transform_result_is_sorted_by_order_id():
    records = [_record(order_id="ORD-9"), _record(order_id="ORD-2"), _record(order_id="ORD-5")]
    transformed, _ = transform(records)
    assert [r.order_id for r in transformed] == ["ORD-2", "ORD-5", "ORD-9"]
