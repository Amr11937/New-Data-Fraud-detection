"""
Load a per-package risk parquet (columns: session_date, account_num,
subscriber_id, package_name, sessions_per_day, download_gb, upload_gb,
total_usage_gb, total_duration_minutes, average_session_duration_minutes,
average_session_usage_gb, anomaly_score, risk_score_0_100, risk_level) into
subscriber_package_daily, then rebuild the package_risk_daily rollup.

Creates the tables if needed (sql/migration_005_package_risk.sql). Safe to
re-run: rows in the file's date range are deleted first.

Usage (DATABASE_URL in env, or --database-url):
    python scripts/load_package_risk.py --input path/to/package_results.parquet
"""
from __future__ import annotations

import argparse
import io
import os
import time
from pathlib import Path

import psycopg2
import pyarrow.parquet as pq
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

load_dotenv()

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"

COLS = [
    "session_date", "account_num", "subscriber_id", "package_name", "sessions_per_day",
    "download_gb", "upload_gb", "total_usage_gb", "total_duration_minutes",
    "average_session_duration_minutes", "average_session_usage_gb", "anomaly_score",
    "risk_score_0_100", "risk_level",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--batch-size", type=int, default=250_000)
    parser.add_argument("--limit-rows", type=int, default=0, help="Load only the first N rows (testing)")
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
    cur.execute((SQL_DIR / "migration_005_package_risk.sql").read_text(encoding="utf-8"))
    conn.commit()

    cur.execute("DELETE FROM subscriber_package_daily WHERE session_date BETWEEN %s AND %s", (d_min, d_max))
    print(f"Cleared {cur.rowcount:,} existing rows in that date range", flush=True)
    conn.commit()

    total, t0 = 0, time.time()
    for batch in pf.iter_batches(batch_size=args.batch_size, columns=COLS):
        df = batch.to_pandas()[COLS]
        if args.limit_rows and total + len(df) > args.limit_rows:
            df = df.iloc[: args.limit_rows - total]
        buf = io.StringIO()
        df.to_csv(buf, index=False, header=False, na_rep="\\N")
        buf.seek(0)
        cur.copy_expert(
            f"COPY subscriber_package_daily ({','.join(COLS)}) FROM STDIN WITH (FORMAT csv, NULL '\\N')", buf
        )
        conn.commit()
        total += len(df)
        print(f"{total:,} rows loaded ({time.time() - t0:.0f}s)", flush=True)
        if args.limit_rows and total >= args.limit_rows:
            break

    print("Rebuilding package_risk_daily rollup...", flush=True)
    cur.execute("TRUNCATE TABLE package_risk_daily")
    cur.execute("""
        INSERT INTO package_risk_daily
            (session_date, package_name, row_count, risk_sum, risk_max, high_count, medium_count, low_count)
        SELECT session_date, package_name, COUNT(*), SUM(risk_score_0_100), MAX(risk_score_0_100),
               SUM(CASE WHEN risk_level = 'HIGH' THEN 1 ELSE 0 END),
               SUM(CASE WHEN risk_level = 'MEDIUM' THEN 1 ELSE 0 END),
               SUM(CASE WHEN risk_level = 'LOW' THEN 1 ELSE 0 END)
        FROM subscriber_package_daily
        GROUP BY session_date, package_name
    """)
    cur.execute("SELECT COUNT(*) FROM package_risk_daily")
    print(f"Rollup rows: {cur.fetchone()[0]:,}", flush=True)
    conn.commit()
    conn.autocommit = True
    cur.execute("ANALYZE subscriber_package_daily")
    conn.close()
    print(f"DONE. Inserted {total:,} rows.")


if __name__ == "__main__":
    main()
