"""etl-pipeline: a small, portfolio-scale ETL tool for messy order data.

Ingests CSV/JSON order exports, validates every record against a strict
schema, quarantines invalid records with a human-readable reason, transforms
and deduplicates the valid ones, and loads the result into a local SQLite
warehouse.
"""

from etl_pipeline.cli import run_pipeline

__all__ = ["run_pipeline"]
__version__ = "0.1.0"
