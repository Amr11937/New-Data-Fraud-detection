"""
One-off loader for a pre-aggregated, ML-scored "final output" parquet
(the shape produced by PCRF's original Isolation Forest pipeline --
session_date, account_num, subscriber_id, sessions_per_day,
daily_usage_gb, ..., risk_score_0_100, anomaly_rank) directly into
subscribers_daily.

This is NOT the raw session-level ingest path (see
app/ingest_core.py / scripts/ingest_daily_dataset.py, which expects
record_opening_time/record_closing_time etc. and runs the full
rule+ensemble scoring). This script loads an already-scored file as-is
and leaves rule_score/ml_score/final_score/decision/triggered_rules
NULL -- run scripts/backfill_ensemble_scores.py afterward to populate
those, same as the original historical load.

Usage:
    python scripts/load_subscribers_daily.py --input path/to/final_output.parquet --truncate

--truncate replaces the entire table's contents; omit it to append
instead (e.g. loading a second, non-overlapping file).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import duckdb  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.ingest_core import refresh_analytics_cache  # noqa: E402

load_dotenv()

COLUMNS = [
    "session_date", "account_num", "subscriber_id", "sessions_per_day",
    "daily_usage_gb", "average_session_usage_gb", "total_duration_minutes",
    "average_session_duration_minutes", "total_input_gb", "total_output_gb",
    "offer_count", "offer_name", "ratio", "risk_score_0_100", "anomaly_rank",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Pre-aggregated, ML-scored .parquet file")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--truncate", action="store_true", help="Truncate subscribers_daily before loading")
    parser.add_argument("--batch-size", type=int, default=5000)
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("DATABASE_URL not set (env var or --database-url)")

    print(f"Reading: {args.input}")
    con = duckdb.connect()
    cols_sql = ", ".join(COLUMNS)
    df = con.execute(f"""
        SELECT {cols_sql}
        FROM read_parquet('{args.input}')
    """).df()
    print(f"Read {len(df):,} rows, dates {sorted(df['session_date'].astype(str).unique().tolist())}")

    # Guard against inf/-inf/NaN in ratio (div-by-zero when total_output_gb
    # is 0), same as ingest_core.aggregate_daily's own Ratio calculation.
    df["ratio"] = df["ratio"].replace([float("inf"), float("-inf")], None)
    df = df.where(df.notnull(), None)

    engine = create_engine(args.database_url)

    if args.truncate:
        print("Truncating subscribers_daily...")
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE subscribers_daily"))

    print(f"Inserting {len(df):,} rows...")
    df.to_sql(
        "subscribers_daily", engine, if_exists="append", index=False,
        method="multi", chunksize=args.batch_size,
    )
    print(f"Done. Inserted {len(df):,} rows.")

    print("Refreshing offer catalog/stats + kpi snapshot + subscriber summary + window snapshots...")
    counts = refresh_analytics_cache(args.database_url)
    print(
        f"Refreshed: {counts['offer_name_tokens']:,} token rows, {counts['offer_stats']:,} offer stats rows, "
        f"{counts['subscriber_summary']:,} subscriber summary rows."
    )

    print("Next: run scripts/backfill_ensemble_scores.py to populate rule_score/ml_score/final_score/decision.")


if __name__ == "__main__":
    main()
