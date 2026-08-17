# etl-pipeline

A small, well-engineered ETL tool that ingests messy real-world-style order data (CSV export +
JSON API dump), validates every record against a strict schema, quarantines invalid records
instead of crashing (with a specific reason logged per rejected row), cleans and deduplicates the
valid records, and loads the result into a local SQLite warehouse.

The point of this project isn't scale — it's demonstrating data-quality discipline: nothing bad
silently makes it into the warehouse, and nothing bad silently disappears either. Every rejected
row is traceable back to its source file, source row, and exact reason.

## How it works

The pipeline runs four stages in sequence, each with a single responsibility:

1. **Extract** (`extract.py`) reads every `.csv` and `.json` file in the source directory into a
   common flat list of raw record dicts, tagging each one with its source file and row number.
2. **Validate** (`validate.py`) runs each raw record through a [pydantic](https://docs.pydantic.dev/)
   schema (`schema.py`). Records that pass become typed `OrderRecord` objects. Records that fail
   are captured as `QuarantinedRecord`s carrying a specific, human-readable reason — e.g.
   `invalid email format: 'not-an-email'` or `quantity must be a positive integer (got -2)`, never
   a generic "validation failed".
3. **Transform** (`transform.py`) deduplicates valid records by `order_id` — the same order can
   legitimately appear twice (once in the CSV export, once in the JSON API dump, or twice within
   one file), so for each duplicate group the pipeline keeps the most recent record by
   `order_date`, breaking ties by which copy has more complete data. It also derives a computed
   `line_total = quantity * unit_price` column.
4. **Load** (`load.py`) upserts the cleaned, transformed records into a SQLite `orders` table
   (creating it if needed) and writes every quarantined row to `quarantine.csv` with its reason.

The schema also normalizes messy input as part of validation: `"$45.00"` and `"45.00"` both parse
to `45.0`, and `2026-01-05`, `01/05/2026`, `2026/01/05`, and `2026-01-05T09:30:00` all normalize
to the same `date`.

## Install

Requires Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -e ".[dev]"
```

## Usage

Run the full pipeline against the bundled sample data:

```bash
etl-pipeline run --source data/raw --dest warehouse.db
```

```
--source   directory containing raw .csv/.json source files (default: data/raw)
--dest     path to the SQLite warehouse database to write (default: warehouse.db)
```

Quarantined rows are written next to the destination database, as `quarantine.csv`.

### Example output

Running it against the bundled `data/raw/orders.csv` (15 rows) and `data/raw/orders.json`
(10 rows) — deliberately messy sample data including malformed emails, negative quantities,
non-numeric prices, missing required fields, unparseable dates, and a duplicate `order_id` shared
across both source files — produces:

```
$ etl-pipeline run --source data/raw --dest warehouse.db
ETL Pipeline Summary
========================================
Rows extracted:            25
Rows valid:                14
Duplicate rows merged:     2
Rows loaded to warehouse:  12  -> warehouse.db
Rows quarantined:          11  -> quarantine.csv

Quarantine reasons:
    2  invalid email format
    1  quantity must be a positive integer
    1  missing required field: customer_email
    1  unit_price is not a valid number
    1  unparseable order_date
    1  missing required field: quantity
    1  missing required field: product_sku
    1  unit_price must be a positive number
    1  quantity must be a whole number
    1  missing required field: order_id
```

25 raw records go in; 11 are quarantined across 10 distinct reasons; 2 duplicate rows (one order
appearing in both the CSV and JSON sources, one appearing twice within the JSON file) collapse
into their most-recent copy; 12 clean, deduplicated rows land in the warehouse.

## Project structure

```
src/etl_pipeline/
  schema.py     pydantic OrderRecord model — field validators for email, quantity, price, date
  extract.py    reads raw CSV/JSON into a common intermediate record format
  validate.py   validates each record; splits into valid records vs. QuarantinedRecords
  transform.py  dedupe by order_id (most recent/complete wins) + computed line_total
  load.py       upserts into SQLite warehouse.db; writes quarantine.csv report
  cli.py        `etl-pipeline run` entry point, prints the summary
data/raw/
  orders.csv    sample CSV export (15 rows, deliberately messy)
  orders.json   sample JSON API dump (10 rows, deliberately messy)
tests/
  test_schema.py               schema validation, one test per valid/invalid case
  test_transform.py            dedup logic + computed line_total
  test_pipeline_end_to_end.py  full run against fixture files, asserts warehouse/quarantine counts
```

## Development

```bash
pytest          # run the test suite (24 tests)
ruff check .    # lint
```

Both must pass before shipping a change; there is no separate CI config for this repo (it's a
local portfolio piece), but the checks are meant to be run before every commit.

## Design notes

- **Pydantic for validation, not just typing.** Every messiness case in the sample data (bad
  email, negative quantity, non-numeric price, missing field, unparseable date, currency-symbol
  price, mixed date formats) is exercised by a dedicated field validator with a specific error
  message, and by a dedicated unit test in `test_schema.py`.
- **Quarantine over crash.** `validate_records` never raises on bad input — every row either
  becomes a typed `OrderRecord` or a `QuarantinedRecord` with a traceable reason, source file, and
  source row.
- **SQLite via the standard library.** `sqlite3` with an `INSERT ... ON CONFLICT DO UPDATE` upsert
  keeps the loader dependency-free and makes re-running the pipeline against updated source data
  idempotent (rows are updated in place by `order_id`, not duplicated).

## License

MIT — see [LICENSE](LICENSE).
