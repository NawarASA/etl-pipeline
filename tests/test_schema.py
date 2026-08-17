"""Tests for the OrderRecord schema: one valid case, one per invalid case."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from etl_pipeline.schema import OrderRecord

VALID_PAYLOAD = {
    "order_id": "ORD-9001",
    "customer_email": "test.user@example.com",
    "product_sku": "SKU-1234",
    "quantity": 2,
    "unit_price": "19.99",
    "order_date": "2026-01-05",
    "status": "completed",
}


def test_valid_record_parses_correctly():
    record = OrderRecord(**VALID_PAYLOAD)
    assert record.order_id == "ORD-9001"
    assert record.customer_email == "test.user@example.com"
    assert record.quantity == 2
    assert record.unit_price == 19.99
    assert record.order_date == date(2026, 1, 5)
    assert record.status == "completed"


@pytest.mark.parametrize(
    "field",
    ["order_id", "customer_email", "product_sku"],
)
def test_missing_required_string_field_is_rejected(field):
    payload = {**VALID_PAYLOAD, field: ""}
    with pytest.raises(ValidationError) as exc_info:
        OrderRecord(**payload)
    assert f"missing required field: {field}" in str(exc_info.value)


def test_missing_order_id_none_is_rejected():
    payload = {**VALID_PAYLOAD, "order_id": None}
    with pytest.raises(ValidationError) as exc_info:
        OrderRecord(**payload)
    assert "missing required field: order_id" in str(exc_info.value)


def test_malformed_email_is_rejected():
    payload = {**VALID_PAYLOAD, "customer_email": "not-an-email"}
    with pytest.raises(ValidationError) as exc_info:
        OrderRecord(**payload)
    assert "invalid email format" in str(exc_info.value)


def test_negative_quantity_is_rejected():
    payload = {**VALID_PAYLOAD, "quantity": -2}
    with pytest.raises(ValidationError) as exc_info:
        OrderRecord(**payload)
    assert "quantity must be a positive integer" in str(exc_info.value)


def test_non_numeric_quantity_is_rejected():
    payload = {**VALID_PAYLOAD, "quantity": "three"}
    with pytest.raises(ValidationError) as exc_info:
        OrderRecord(**payload)
    assert "quantity must be a whole number" in str(exc_info.value)


def test_negative_price_is_rejected():
    payload = {**VALID_PAYLOAD, "unit_price": "-8.25"}
    with pytest.raises(ValidationError) as exc_info:
        OrderRecord(**payload)
    assert "unit_price must be a positive number" in str(exc_info.value)


def test_non_numeric_price_is_rejected():
    payload = {**VALID_PAYLOAD, "unit_price": "abc"}
    with pytest.raises(ValidationError) as exc_info:
        OrderRecord(**payload)
    assert "unit_price is not a valid number" in str(exc_info.value)


def test_unparseable_date_is_rejected():
    payload = {**VALID_PAYLOAD, "order_date": "not-a-date"}
    with pytest.raises(ValidationError) as exc_info:
        OrderRecord(**payload)
    assert "unparseable order_date" in str(exc_info.value)


@pytest.mark.parametrize(
    "raw_date,expected",
    [
        ("2026-01-05", date(2026, 1, 5)),
        ("01/05/2026", date(2026, 1, 5)),
        ("2026/01/05", date(2026, 1, 5)),
        ("2026-01-05T09:30:00", date(2026, 1, 5)),
    ],
)
def test_multiple_date_formats_are_normalized(raw_date, expected):
    payload = {**VALID_PAYLOAD, "order_date": raw_date}
    record = OrderRecord(**payload)
    assert record.order_date == expected


def test_price_with_currency_symbol_is_coerced():
    payload = {**VALID_PAYLOAD, "unit_price": "$45.00"}
    record = OrderRecord(**payload)
    assert record.unit_price == 45.00


def test_unrecognized_status_falls_back_to_unknown():
    payload = {**VALID_PAYLOAD, "status": "backordered"}
    record = OrderRecord(**payload)
    assert record.status == "unknown"
