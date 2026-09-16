"""
One-time backfill: computes rule_score / ml_score / final_score /
decision / triggered_rules for existing subscribers_daily rows that
predate migration_001_merge_ensemble.sql (i.e. rows where decision IS
NULL). New rows get these fields at ingest time automatically
(app/ingest_core.py) -- this script is only for the historical
615k+ rows already in the table.

Usage:
    python scripts/backfill_ensemble_scores.py --batch-size 5000

Safe to re-run: only touches rows where decision IS NULL, so an
interrupted run just picks up where it left off.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.ensemble import ensemble_predict  # noqa: E402
from app.rules import rule_based_score  # noqa: E402

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("DATABASE_URL not set (env var or --database-url)")

    engine = create_engine(args.database_url)
    total_updated = 0

    while True:
        with engine.begin() as conn:
            rows = conn.execute(text(f"""
                SELECT id, daily_usage_gb, total_input_gb, total_output_gb,
                       average_session_usage_gb, sessions_per_day, offer_count,
                       ratio, risk_score_0_100
                FROM subscribers_daily
                WHERE decision IS NULL
                LIMIT {args.batch_size}
            """)).mappings().all()

            if not rows:
                break

            for row in rows:
                data = {
                    "daily_usage_gb": row["daily_usage_gb"],
                    "total_input_gb": row["total_input_gb"],
                    "total_output_gb": row["total_output_gb"],
                    "average_session_usage_gb": row["average_session_usage_gb"],
                    "sessions_per_day": row["sessions_per_day"],
                    "offer_count": row["offer_count"],
                    "Ratio": row["ratio"],
                }
                rule_score, triggered, hard_block = rule_based_score(data)
                ml_score = float(row["risk_score_0_100"]) / 100.0
                result = ensemble_predict(rule_score, ml_score, hard_block=hard_block)

                conn.execute(
                    text("""
                        UPDATE subscribers_daily
                        SET rule_score = :rule_score, ml_score = :ml_score,
                            final_score = :final_score, decision = :decision,
                            triggered_rules = :triggered_rules
                        WHERE id = :id
                    """),
                    {
                        "id": row["id"],
                        "rule_score": result["rule_score"],
                        "ml_score": result["ml_score"],
                        "final_score": result["final_score"],
                        "decision": result["decision"],
                        "triggered_rules": ", ".join(triggered),
                    },
                )

            total_updated += len(rows)
            print(f"Backfilled {total_updated:,} rows so far...")

    print(f"Done. Total rows backfilled: {total_updated:,}")


if __name__ == "__main__":
    main()
