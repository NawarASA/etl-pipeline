"""Pydantic schema for a single validated order record.

This is the contract every raw row (from CSV or JSON, regardless of source
messiness) must satisfy before it is allowed into the warehouse. Anything
that fails validation is quarantined with the specific reason it failed,
rather than crashing the pipeline.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Source data uses a mix of date formats (CSV export vs. JSON API dump), so
# we try each of these in order until one parses.
_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%Y/%m/%d",
)

VALID_STATUSES = {"pending", "completed", "shipped", "cancelled"}


def _blank_to_none(value: object) -> object | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


class OrderRecord(BaseModel):
    """A single validated e-commerce order line."""

    model_config = ConfigDict(str_strip_whitespace=True)

    order_id: str
    customer_email: str
    product_sku: str
    quantity: int
    unit_price: float
    order_date: date
    status: str = "unknown"

    # Traceability metadata, not part of the "business" data.
    source_file: str | None = None
    source_row: int | None = None

    @field_validator("order_id", "customer_email", "product_sku", mode="before")
    @classmethod
    def _required_string(cls, value: object, info) -> str:
        value = _blank_to_none(value)
        if value is None:
            raise ValueError(f"missing required field: {info.field_name}")
        return str(value)

    @field_validator("customer_email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        if not _EMAIL_RE.match(value):
            raise ValueError(f"invalid email format: '{value}'")
        return value.lower()

    @field_validator("quantity", mode="before")
    @classmethod
    def _parse_quantity(cls, value: object) -> int:
        value = _blank_to_none(value)
        if value is None:
            raise ValueError("missing required field: quantity")
        try:
            quantity = int(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError(f"quantity must be a whole number (got '{value}')") from exc
        if quantity <= 0:
            raise ValueError(f"quantity must be a positive integer (got {quantity})")
        return quantity

    @field_validator("unit_price", mode="before")
    @classmethod
    def _parse_price(cls, value: object) -> float:
        value = _blank_to_none(value)
        if value is None:
            raise ValueError("missing required field: unit_price")
        cleaned = str(value).strip().replace("$", "").replace(",", "")
        try:
            price = float(cleaned)
        except ValueError as exc:
            raise ValueError(f"unit_price is not a valid number (got '{value}')") from exc
        if price <= 0:
            raise ValueError(f"unit_price must be a positive number (got {price})")
        return price

    @field_validator("order_date", mode="before")
    @classmethod
    def _parse_date(cls, value: object) -> date:
        value = _blank_to_none(value)
        if value is None:
            raise ValueError("missing required field: order_date")
        if isinstance(value, date):
            return value
        text = str(value).strip()
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"unparseable order_date: '{value}'")

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value: object) -> str:
        value = _blank_to_none(value)
        if value is None:
            return "unknown"
        normalized = str(value).strip().lower()
        return normalized if normalized in VALID_STATUSES else "unknown"
