"""
Load a per-package risk parquet (columns: session_date, account_num,
subscriber_id, package_name, sessions_per_day, download_gb, upload_gb,
total_usage_gb, total_duration_minutes, average_session_duration_minutes,
average_session_usage_gb, anomaly_score, risk_score_0_100, risk_level) into
subscriber_package_daily, then rebuild the package_risk_daily rollup.

Creates the tables if needed (sql/migration_005_package_risk.sql). Safe to
re-run: rows for the dates being loaded are deleted first. Only those dates are
touched, so files covering different days can be loaded one after another.

A date is refused if the database already holds far more rows for it than the
file does (e.g. the file's last day is a partial day): use --date-from /
--date-to to leave it out, or --force to replace it anyway.

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
    parser.add_argument("--date-from", help="Only load rows on/after this date (YYYY-MM-DD)")
    parser.add_argument("--date-to", help="Only load rows on/before this date (YYYY-MM-DD)")
    parser.add_argument("--force", action="store_true", help="Replace a date even if the DB holds many more rows for it")
    parser.add_argument("--limit-rows", type=int, default=0, help="Load only the first N rows (testing)")
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("DATABASE_URL not set (env var or --database-url)")

    pf = pq.ParquetFile(args.input)
    dates = pf.read(columns=["session_date"]).column("session_date").to_pandas().astype(str)
    if args.date_from:
        dates = dates[dates >= args.date_from]
    if args.date_to:
        dates = dates[dates <= args.date_to]
    if dates.empty:
        raise SystemExit("No rows in the requested date range")
    d_min, d_max = dates.min(), dates.max()
    file_counts = dates.value_counts().sort_index()
    print(f"{len(dates):,} of {pf.metadata.num_rows:,} rows, {d_min} .. {d_max}", flush=True)

    u = make_url(args.database_url)
    conn = psycopg2.connect(host=u.host, port=u.port, user=u.username, password=u.password,
                            dbname=u.database, connect_timeout=15)
    cur = conn.cursor()
    cur.execute((SQL_DIR / "migration_005_package_risk.sql").read_text(encoding="utf-8"))
    conn.commit()

    cur.execute(
        "SELECT session_date::text, COUNT(*) FROM subscriber_package_daily "
        "WHERE session_date BETWEEN %s AND %s GROUP BY session_date",
        (d_min, d_max),
    )
    existing = dict(cur.fetchall())
    for d, n_file in file_counts.items():
        n_db = existing.get(d, 0)
        print(f"  {d}: file {n_file:,} rows, database {n_db:,} rows", flush=True)
        if n_db > 2 * n_file and not args.force:
            raise SystemExit(
                f"Refusing to replace {d}: the database has {n_db:,} rows but the file only {n_file:,} "
                "(partial day?). Use --date-to to skip it, or --force to replace it."
            )

    cur.execute("DELETE FROM subscriber_package_daily WHERE session_date BETWEEN %s AND %s", (d_min, d_max))
    print(f"Cleared {cur.rowcount:,} existing rows in that date range", flush=True)
    conn.commit()

    total, t0 = 0, time.time()
    for batch in pf.iter_batches(batch_size=args.batch_size, columns=COLS):
        df = batch.to_pandas()[COLS]
        day = df["session_date"].astype(str)
        df = df[(day >= d_min) & (day <= d_max)]
        if df.empty:
            continue
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
