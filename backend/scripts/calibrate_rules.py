"""
Derives real percentile-based rule thresholds from the live
subscribers_daily table, to replace the placeholder values shipped in
app/config/rules.yaml (which are just 5x-median guesses).

Usage:
    python scripts/calibrate_rules.py --percentile 95

Prints a ready-to-paste rules.yaml block using each feature's actual
p95 (or whichever percentile you choose) as the upper_limit -- i.e.
"flag the top 5% of subscribers by this feature", which is a much more
defensible cutoff than a flat multiple of the median.

Points-per-rule are NOT recalculated here -- those encode a judgment
call about severity that data alone can't make. Adjust by hand once
you see real trigger rates from /api/analytics/rule-statistics.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

load_dotenv()

FEATURES = {
    "rule_01": "daily_usage_gb",
    "rule_02": "total_input_gb",
    "rule_03": "total_output_gb",
    "rule_04": "average_session_usage_gb",
    "rule_05": "sessions_per_day",
    "rule_06": "offer_count",
    "rule_07": "ratio",  # lowercase: actual Postgres column name
}

POINTS = {  # unchanged from the shipped rules.yaml -- edit by hand as needed
    "rule_01": 15, "rule_02": 10, "rule_03": 10, "rule_04": 20,
    "rule_05": 25, "rule_06": 15, "rule_07": 5,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--percentile", type=float, default=95.0, help="0-100, e.g. 95 = flag the top 5%%")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("DATABASE_URL not set (env var or --database-url)")

    engine = create_engine(args.database_url)
    fraction = args.percentile / 100.0

    print(f"-- Recommended rules.yaml (p{args.percentile:.0f} thresholds, computed {os_now()})")
    print()

    with engine.connect() as conn:
        for rule_id, feature in FEATURES.items():
            sql = text(f"""
                SELECT percentile_cont(:fraction) WITHIN GROUP (ORDER BY {feature})
                FROM subscribers_daily
                WHERE {feature} IS NOT NULL
            """)
            value = conn.execute(sql, {"fraction": fraction}).scalar_one()
            display_feature = "Ratio" if feature == "ratio" else feature
            print(f"{rule_id}:")
            print(f"  feature: {display_feature}")
            print(f"  upper_limit: {round(float(value), 6)}")
            print(f"  points: {POINTS[rule_id]}")
            print()

    print("max_raw_score: 100")


def os_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


if __name__ == "__main__":
    main()
