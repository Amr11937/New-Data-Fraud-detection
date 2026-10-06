"""
Append a pre-aggregated, ML-scored "final output" parquet (same shape as
scripts/load_subscribers_daily.py expects) to subscribers_daily, computing
rule_score / ml_score / final_score / decision / triggered_rules in the same
pass so no separate backfill is needed.

Differs from load_subscribers_daily.py in that it streams the file in
batches and uses COPY (fast over a remote link), and it scores rows with
the app's own rules.py / ensemble.py before inserting.

Safe to re-run: rows whose session_date falls within the file's date range
are deleted first, so an interrupted run never leaves duplicates.

Usage (DATABASE_URL in env, or --database-url):
    python scripts/load_scored_parquet.py --input path/to/final_output.parquet
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np  # noqa: E402
import psycopg2  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.ensemble import ensemble_predict  # noqa: E402
from app.ingest_core import refresh_analytics_cache  # noqa: E402
from app.rules import rule_based_score  # noqa: E402

load_dotenv()

COLS = [
    "session_date", "account_num", "subscriber_id", "sessions_per_day", "daily_usage_gb",
    "average_session_usage_gb", "total_duration_minutes", "average_session_duration_minutes",
    "total_input_gb", "total_output_gb", "offer_count", "offer_name", "ratio",
    "risk_score_0_100", "anomaly_rank", "rule_score", "ml_score", "final_score",
    "decision", "triggered_rules",
]


def score(df):
    rule_scores, ml_scores, final_scores, decisions, triggered_lists = [], [], [], [], []
    for r in df.itertuples(index=False):
        data = {
            "daily_usage_gb": r.daily_usage_gb, "total_input_gb": r.total_input_gb,
            "total_output_gb": r.total_output_gb, "average_session_usage_gb": r.average_session_usage_gb,
            "sessions_per_day": r.sessions_per_day, "offer_count": r.offer_count, "Ratio": r.ratio,
        }
        rule_score, triggered, hard_block = rule_based_score(data)
        result = ensemble_predict(rule_score, float(r.risk_score_0_100) / 100.0, hard_block=hard_block)
        rule_scores.append(result["rule_score"])
        ml_scores.append(result["ml_score"])
        final_scores.append(result["final_score"])
        decisions.append(result["decision"])
        triggered_lists.append(", ".join(triggered))
    df["rule_score"], df["ml_score"], df["final_score"] = rule_scores, ml_scores, final_scores
    df["decision"], df["triggered_rules"] = decisions, triggered_lists
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--batch-size", type=int, default=200_000)
    parser.add_argument("--skip-refresh", action="store_true", help="Skip rebuilding the cached analytics tables")
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("DATABASE_URL not set (env var or --database-url)")

    pf = pq.ParquetFile(args.input)
    dates = pf.read(columns=["session_date"]).column("session_date").to_pandas()
    d_min, d_max = dates.min(), dates.max()
    print(f"{pf.metadata.num_rows:,} rows, {d_min} .. {d_max}", flush=True)

    u = make_url(args.database_url)
    conn = psycopg2.connect(host=u.host, port=u.port, user=u.username, password=u.password,
                            dbname=u.database, connect_timeout=15)
    cur = conn.cursor()
    cur.execute("DELETE FROM subscribers_daily WHERE session_date BETWEEN %s AND %s", (d_min, d_max))
    print(f"Cleared {cur.rowcount:,} existing rows in that date range", flush=True)
    conn.commit()

    total, t0 = 0, time.time()
    for batch in pf.iter_batches(batch_size=args.batch_size):
        df = batch.to_pandas()
        df["ratio"] = df["ratio"].replace([np.inf, -np.inf], np.nan)
        df["anomaly_rank"] = df["anomaly_rank"].astype("Int64")
        df = score(df)[COLS]
        buf = io.StringIO()
        df.to_csv(buf, index=False, header=False, na_rep="\\N")
        buf.seek(0)
        cur.copy_expert(
            f"COPY subscribers_daily ({','.join(COLS)}) FROM STDIN WITH (FORMAT csv, NULL '\\N')", buf
        )
        conn.commit()
        total += len(df)
        print(f"{total:,} rows loaded ({time.time() - t0:.0f}s)", flush=True)
    conn.close()

    if not args.skip_refresh:
        print("Refreshing cached analytics tables (can take a few minutes)...", flush=True)
        counts = refresh_analytics_cache(args.database_url)
        print(f"Refreshed: {counts}", flush=True)
    print(f"DONE. Inserted {total:,} rows.")


if __name__ == "__main__":
    main()
