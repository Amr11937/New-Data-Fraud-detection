"""
Manual/local CLI for ingesting a raw daily dataset.

Usage:
    python scripts/ingest_daily_dataset.py --input raw_daily_2026-08-19.parquet

Expects DATABASE_URL in the environment, or pass --database-url.
See app/ingest_core.py for the actual pipeline (shared with the
automatic S3-triggered Lambda in app/ingest_handler.py).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv  # noqa: E402

from app.ingest_core import run_ingestion  # noqa: E402

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Raw daily session-level .parquet or .csv file")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("DATABASE_URL not set (env var or --database-url)")

    print(f"Ingesting: {args.input}")
    result = run_ingestion(args.input, args.database_url)
    print(f"Inserted {result['rows_ingested']:,} rows for dates {result['dates']}")
    print(f"Risk score range: {result['risk_min']:.2f} - {result['risk_max']:.2f}")


if __name__ == "__main__":
    main()
