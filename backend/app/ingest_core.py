"""
Shared ingestion logic: raw daily session-level file -> aggregated,
scored rows ready to insert into subscribers_daily.

Extended from PCRF's original ingest_core.py: after the Isolation
Forest scores a batch, each row is also run through the rule engine
and the weighted ensemble, adding rule_score / ml_score / final_score
/ decision / triggered_rules before insert.

Used by both scripts/ingest_daily_dataset.py (manual/local runs) and
app/ingest_worker.py (the background S3-polling task that replaced the
old S3-triggered ingest Lambda).
"""
from __future__ import annotations

import duckdb
import pandas as pd

from .ensemble import ensemble_predict
from .model_service import model_service
from .rules import rule_based_score


def load_and_clean(input_path: str):
    con = duckdb.connect()
    reader = "read_parquet" if input_path.endswith(".parquet") else "read_csv_auto"

    con.execute(f"""
        CREATE OR REPLACE TEMP VIEW raw_sessions AS
        SELECT
            account_num,
            subscriber_id,
            TRY_CAST(record_opening_time AS TIMESTAMP) AS record_opening_time,
            TRY_CAST(record_closing_time AS TIMESTAMP) AS record_closing_time,
            session_id,
            cc_input_octets_bytes,
            cc_output_octets_bytes,
            offer_name
        FROM {reader}('{input_path}')
    """)

    con.execute("""
        CREATE OR REPLACE TEMP VIEW cleaned AS
        SELECT DISTINCT
            account_num, subscriber_id, record_opening_time, record_closing_time,
            session_id, cc_input_octets_bytes, cc_output_octets_bytes, offer_name
        FROM raw_sessions
        WHERE record_opening_time IS NOT NULL
          AND record_closing_time IS NOT NULL
          AND record_closing_time >= record_opening_time
    """)
    return con


def aggregate_daily(con) -> pd.DataFrame:
    con.execute("""
        CREATE OR REPLACE TEMP VIEW usage_duration AS
        SELECT
            account_num, subscriber_id,
            CAST(record_opening_time AS DATE) AS session_date,
            offer_name,
            (CAST(cc_input_octets_bytes AS DOUBLE) + CAST(cc_output_octets_bytes AS DOUBLE))
                / 1073741824.0 AS total_usage_gb,
            CAST(cc_input_octets_bytes AS DOUBLE) / 1073741824.0 AS input_gb,
            CAST(cc_output_octets_bytes AS DOUBLE) / 1073741824.0 AS output_gb,
            date_diff('second', record_opening_time, record_closing_time) / 60.0 AS duration_minutes
        FROM cleaned
    """)

    daily = con.sql("""
        SELECT
            session_date, account_num, subscriber_id,
            COUNT(*) AS sessions_per_day,
            SUM(total_usage_gb) AS daily_usage_gb,
            AVG(total_usage_gb) AS average_session_usage_gb,
            SUM(duration_minutes) AS total_duration_minutes,
            AVG(duration_minutes) AS average_session_duration_minutes,
            SUM(input_gb) AS total_input_gb,
            SUM(output_gb) AS total_output_gb,
            COUNT(DISTINCT offer_name) AS offer_count,
            STRING_AGG(DISTINCT offer_name, ', ') AS offer_name
        FROM usage_duration
        GROUP BY session_date, account_num, subscriber_id
    """).df()

    mode_offer = con.sql("""
        WITH counts AS (
            SELECT session_date, account_num, subscriber_id, offer_name,
                   COUNT(*) AS offer_sessions_per_day
            FROM usage_duration
            WHERE offer_name IS NOT NULL AND TRIM(offer_name) <> ''
            GROUP BY session_date, account_num, subscriber_id, offer_name
        )
        SELECT session_date, account_num, subscriber_id, offer_name AS mode_offer_name
        FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY session_date, account_num, subscriber_id
                ORDER BY offer_sessions_per_day DESC, offer_name
            ) AS rn
            FROM counts
        )
        WHERE rn = 1
    """).df()

    merged = daily.merge(
        mode_offer, on=["session_date", "account_num", "subscriber_id"], how="left"
    )

    merged["Ratio"] = merged.apply(
        lambda row: None if row["total_output_gb"] == 0 else row["total_input_gb"] / row["total_output_gb"],
        axis=1,
    )
    return merged


def score_batch(daily_df: pd.DataFrame) -> pd.DataFrame:
    """ML scoring (unchanged from PCRF) plus rule engine + ensemble per row."""
    scored = model_service.score_dataframe(daily_df, mode_offer_column="mode_offer_name")

    rule_scores, ml_scores, final_scores, decisions, triggered_lists = [], [], [], [], []
    for _, row in scored.iterrows():
        rule_score, triggered, hard_block = rule_based_score(row.to_dict())
        ml_score = float(row["risk_score_0_100"]) / 100.0
        result = ensemble_predict(rule_score, ml_score, hard_block=hard_block)

        rule_scores.append(result["rule_score"])
        ml_scores.append(result["ml_score"])
        final_scores.append(result["final_score"])
        decisions.append(result["decision"])
        triggered_lists.append(", ".join(triggered))

    scored["rule_score"] = rule_scores
    scored["ml_score"] = ml_scores
    scored["final_score"] = final_scores
    scored["decision"] = decisions
    scored["triggered_rules"] = triggered_lists
    return scored


def bulk_insert(df: pd.DataFrame, database_url: str) -> int:
    from sqlalchemy import create_engine

    engine = create_engine(database_url)
    insert_cols = [
        "session_date", "account_num", "subscriber_id", "sessions_per_day",
        "daily_usage_gb", "average_session_usage_gb", "total_duration_minutes",
        "average_session_duration_minutes", "total_input_gb", "total_output_gb",
        "offer_count", "offer_name", "ratio", "risk_score_0_100", "anomaly_rank",
        "rule_score", "ml_score", "final_score", "decision", "triggered_rules",
    ]
    to_write = df.rename(columns={"Ratio": "ratio"})[insert_cols].copy()
    to_write["anomaly_rank"] = None

    to_write.to_sql("subscribers_daily", engine, if_exists="append", index=False, method="multi", chunksize=5000)
    return len(to_write)


def run_ingestion(input_path: str, database_url: str) -> dict:
    """End-to-end: raw file path -> rows inserted. Returns a summary
    including which rows need a WebSocket alert (review/block)."""
    con = load_and_clean(input_path)
    daily_df = aggregate_daily(con)
    scored_df = score_batch(daily_df)
    inserted = bulk_insert(scored_df, database_url)

    alertable = scored_df[scored_df["decision"].isin(["REVIEW", "BLOCK"])]
    alerts = [
        {
            "subscriber_id": r["subscriber_id"],
            "account_num": r["account_num"],
            "session_date": str(r["session_date"]),
            "decision": r["decision"],
            "final_score": float(r["final_score"]),
            "triggered_rules": r["triggered_rules"],
        }
        for _, r in alertable.iterrows()
    ]

    return {
        "rows_ingested": inserted,
        "risk_min": float(scored_df["risk_score_0_100"].min()) if inserted else None,
        "risk_max": float(scored_df["risk_score_0_100"].max()) if inserted else None,
        "dates": sorted(scored_df["session_date"].astype(str).unique().tolist()),
        "alerts": alerts,
    }
