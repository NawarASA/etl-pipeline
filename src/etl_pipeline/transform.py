"""Transform valid records: dedupe by order_id and derive computed columns.

Duplicate order_ids can occur *within* a single source file or *across* the
two source formats (the same order showing up in both the CSV export and
the JSON API dump). For each duplicate group we keep the most recent
(latest order_date) record, breaking ties by which one is more complete
(has a recognized, non-default status).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from etl_pipeline.schema import OrderRecord


@dataclass
class TransformedOrder:
    order_id: str
    customer_email: str
    product_sku: str
    quantity: int
    unit_price: float
    order_date: date
    status: str
    line_total: float


def _completeness(record: OrderRecord) -> int:
    """Higher is more complete. Used only to break order_date ties."""
    return 1 if record.status != "unknown" else 0


def _is_better(candidate: OrderRecord, current_best: OrderRecord) -> bool:
    if candidate.order_date != current_best.order_date:
        return candidate.order_date > current_best.order_date
    return _completeness(candidate) > _completeness(current_best)


def dedupe(records: list[OrderRecord]) -> tuple[list[OrderRecord], int]:
    """Collapse records that share an order_id, keeping the best one.

    Returns (deduped_records, number_of_duplicate_rows_removed).
    """
    best_by_id: dict[str, OrderRecord] = {}
    for record in records:
        current_best = best_by_id.get(record.order_id)
        if current_best is None or _is_better(record, current_best):
            best_by_id[record.order_id] = record

    deduped = list(best_by_id.values())
    duplicates_removed = len(records) - len(deduped)
    return deduped, duplicates_removed


def transform(records: list[OrderRecord]) -> tuple[list[TransformedOrder], int]:
    """Dedupe and enrich valid records with a computed line_total.

    Returns (transformed_records, number_of_duplicate_rows_removed).
    """
    deduped, duplicates_removed = dedupe(records)

    transformed = [
        TransformedOrder(
            order_id=record.order_id,
            customer_email=record.customer_email,
            product_sku=record.product_sku,
            quantity=record.quantity,
            unit_price=record.unit_price,
            order_date=record.order_date,
            status=record.status,
            line_total=round(record.quantity * record.unit_price, 2),
        )
        for record in deduped
    ]
    transformed.sort(key=lambda t: t.order_id)
    return transformed, duplicates_removed
