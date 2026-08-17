"""Validate raw records against the OrderRecord schema.

Valid records pass through as OrderRecord instances. Invalid ones are
captured as QuarantinedRecord objects carrying a specific, human-readable
reason -- never a generic "validation failed".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from etl_pipeline.schema import OrderRecord

# Strips the dynamic, offending value off a reason string so similar
# failures (e.g. two different bad emails) group into one category for the
# summary report. Cuts at the first "(" or at a quoted value after ": ".
_CATEGORY_SPLIT_RE = re.compile(r"\s*\(|:\s*'")


@dataclass
class QuarantinedRecord:
    raw: dict[str, Any]
    reason: str
    source_file: str | None = None
    source_row: int | None = None
    order_id: str | None = field(default=None)

    def __post_init__(self) -> None:
        if self.order_id is None:
            self.order_id = self.raw.get("order_id")


def categorize(reason: str) -> str:
    """Collapse a full reason string down to a stable category label,
    e.g. "invalid email format: 'x@y'" -> "invalid email format".
    """
    first_error = reason.split(";")[0].strip()
    return _CATEGORY_SPLIT_RE.split(first_error)[0].strip()


def validate_records(
    raw_records: list[dict[str, Any]],
) -> tuple[list[OrderRecord], list[QuarantinedRecord]]:
    """Validate each raw record. Returns (valid_records, quarantined_records)."""
    valid: list[OrderRecord] = []
    quarantined: list[QuarantinedRecord] = []

    for raw in raw_records:
        try:
            record = OrderRecord(**raw)
        except ValidationError as exc:
            reason = "; ".join(_clean_message(err["msg"]) for err in exc.errors())
            quarantined.append(
                QuarantinedRecord(
                    raw=raw,
                    reason=reason,
                    source_file=raw.get("source_file"),
                    source_row=raw.get("source_row"),
                )
            )
        else:
            valid.append(record)

    return valid, quarantined


def _clean_message(msg: str) -> str:
    # Pydantic v2 prefixes custom ValueError messages with "Value error, ".
    prefix = "Value error, "
    return msg[len(prefix) :] if msg.startswith(prefix) else msg
