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

from datetime import timedelta

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


def refresh_offer_catalog(database_url: str) -> dict:
    """Rebuild offer_name_tokens and offer_stats (see
    sql/migration_002_offer_catalog.sql) from the current subscribers_daily
    contents. offer_name_tokens dedupes offer_name first (~128k distinct
    combos out of millions of rows) then unnests only those, so
    date-filtered package counts (GET /api/kpis) stay cheap at request
    time. offer_stats precomputes the GROUP BY single_offer stats used by
    GET /api/analytics/packages (which has no date filter) -- the
    COUNT(DISTINCT subscriber_id) in there is expensive regardless of join
    strategy, so it's computed here once per refresh instead of once per
    request."""
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE offer_name_tokens"))
        conn.execute(text("""
            INSERT INTO offer_name_tokens (offer_name, single_offer)
            SELECT DISTINCT d.offer_name, single_offer
            FROM (
                SELECT DISTINCT offer_name FROM subscribers_daily
                WHERE offer_name IS NOT NULL AND offer_name <> ''
            ) d,
            LATERAL unnest(string_to_array(d.offer_name, ', ')) AS single_offer
        """))
        token_count = conn.execute(text("SELECT COUNT(*) FROM offer_name_tokens")).scalar_one()

        conn.execute(text("TRUNCATE TABLE offer_stats"))
        conn.execute(text("""
            INSERT INTO offer_stats (single_offer, subscriber_count, usage_gb)
            SELECT t.single_offer, COUNT(DISTINCT s.subscriber_id),
                   SUM(s.daily_usage_gb / NULLIF(s.offer_count, 0))
            FROM subscribers_daily s
            JOIN offer_name_tokens t ON t.offer_name = s.offer_name
            GROUP BY t.single_offer
        """))
        stats_count = conn.execute(text("SELECT COUNT(*) FROM offer_stats")).scalar_one()

    return {"offer_name_tokens": token_count, "offer_stats": stats_count}


def refresh_kpi_snapshot(database_url: str) -> None:
    """Rebuild the single-row kpi_snapshot (see
    sql/migration_003_kpi_snapshot.sql) used by GET /api/kpis for its
    default, unfiltered (date_from/date_to both None) call -- the slow
    path at 4.5M+ rows. Must run after refresh_offer_catalog, since it
    reads total_packages from offer_name_tokens."""
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO kpi_snapshot (
                id, total_records, total_subscribers, total_packages, total_sessions,
                total_upload_gb, total_download_gb, total_usage_gb,
                average_risk, maximum_risk, active_days,
                block_count, review_count, allow_count, refreshed_at
            )
            SELECT
                1,
                COUNT(*),
                COUNT(DISTINCT subscriber_id),
                (SELECT COUNT(DISTINCT single_offer) FROM offer_name_tokens),
                COALESCE(SUM(sessions_per_day), 0),
                COALESCE(SUM(total_output_gb), 0),
                COALESCE(SUM(total_input_gb), 0),
                COALESCE(SUM(daily_usage_gb), 0),
                COALESCE(AVG(risk_score_0_100), 0),
                COALESCE(MAX(risk_score_0_100), 0),
                COUNT(DISTINCT session_date),
                SUM(CASE WHEN decision = 'BLOCK' THEN 1 ELSE 0 END),
                SUM(CASE WHEN decision = 'REVIEW' THEN 1 ELSE 0 END),
                SUM(CASE WHEN decision = 'ALLOW' THEN 1 ELSE 0 END),
                now()
            FROM subscribers_daily
            ON CONFLICT (id) DO UPDATE SET
                total_records = EXCLUDED.total_records,
                total_subscribers = EXCLUDED.total_subscribers,
                total_packages = EXCLUDED.total_packages,
                total_sessions = EXCLUDED.total_sessions,
                total_upload_gb = EXCLUDED.total_upload_gb,
                total_download_gb = EXCLUDED.total_download_gb,
                total_usage_gb = EXCLUDED.total_usage_gb,
                average_risk = EXCLUDED.average_risk,
                maximum_risk = EXCLUDED.maximum_risk,
                active_days = EXCLUDED.active_days,
                block_count = EXCLUDED.block_count,
                review_count = EXCLUDED.review_count,
                allow_count = EXCLUDED.allow_count,
                refreshed_at = EXCLUDED.refreshed_at
        """))


def refresh_subscriber_summary(database_url: str) -> int:
    """Rebuild subscriber_summary (see
    sql/migration_004_subscriber_dashboard_cache.sql): one row per
    subscriber with their latest record, history length, and max risk
    score, computed in a single pass (window functions + DISTINCT ON)
    instead of the 3 separate full-table scans GET /api/subscribers and
    GET /api/analytics/risk-distribution used to run per request."""
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE subscriber_summary"))
        conn.execute(text("""
            INSERT INTO subscriber_summary (
                subscriber_id, account_num, latest_session_date, latest_risk_score_0_100,
                latest_sessions_per_day, latest_daily_usage_gb, latest_rule_score, latest_ml_score,
                latest_final_score, latest_decision, latest_triggered_rules,
                history_days, max_risk_score_0_100
            )
            SELECT DISTINCT ON (subscriber_id)
                subscriber_id, account_num, session_date, risk_score_0_100,
                sessions_per_day, daily_usage_gb, rule_score, ml_score,
                final_score, decision, triggered_rules,
                day_count, max_risk
            FROM (
                SELECT *,
                    COUNT(*) OVER (PARTITION BY subscriber_id) AS day_count,
                    MAX(risk_score_0_100) OVER (PARTITION BY subscriber_id) AS max_risk
                FROM subscribers_daily
            ) x
            ORDER BY subscriber_id, session_date DESC
        """))
        return conn.execute(text("SELECT COUNT(*) FROM subscriber_summary")).scalar_one()


def refresh_window_snapshots(database_url: str) -> None:
    """Rebuild window_snapshot (see
    sql/migration_004_subscriber_dashboard_cache.sql) with the last-7/
    last-30-day summaries GET /api/analytics/windows serves. Mirrors the
    live _window_summary() query in app/routers/dashboard.py."""
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url)
    window_sql = """
        SELECT
            COUNT(DISTINCT subscriber_id)      AS total_subscribers,
            COALESCE(SUM(sessions_per_day), 0) AS total_sessions,
            COALESCE(AVG(risk_score_0_100), 0) AS average_risk,
            COALESCE(MAX(risk_score_0_100), 0) AS maximum_risk,
            COALESCE(SUM(daily_usage_gb), 0)   AS total_usage_gb,
            COUNT(DISTINCT session_date)       AS days_with_data,
            SUM(CASE WHEN decision = 'BLOCK' THEN 1 ELSE 0 END)  AS block_count,
            SUM(CASE WHEN decision = 'REVIEW' THEN 1 ELSE 0 END) AS review_count
        FROM subscribers_daily
        WHERE session_date >= :date_from AND session_date <= :date_to
    """
    with engine.begin() as conn:
        latest = conn.execute(text("SELECT MAX(session_date) FROM subscribers_daily")).scalar_one()
        conn.execute(text("TRUNCATE TABLE window_snapshot"))
        if latest is None:
            return

        for label, days in (("last_7_days", 7), ("last_30_days", 30)):
            date_from = latest - timedelta(days=days - 1)
            row = conn.execute(text(window_sql), {"date_from": date_from, "date_to": latest}).mappings().one()
            conn.execute(text("""
                INSERT INTO window_snapshot (
                    label, date_from, date_to, as_of_date, days_with_data,
                    total_subscribers, total_sessions, average_risk, maximum_risk,
                    total_usage_gb, block_count, review_count
                ) VALUES (
                    :label, :date_from, :date_to, :as_of_date, :days_with_data,
                    :total_subscribers, :total_sessions, :average_risk, :maximum_risk,
                    :total_usage_gb, :block_count, :review_count
                )
            """), {
                "label": label, "date_from": date_from, "date_to": latest, "as_of_date": latest,
                "days_with_data": row["days_with_data"], "total_subscribers": row["total_subscribers"],
                "total_sessions": row["total_sessions"], "average_risk": row["average_risk"],
                "maximum_risk": row["maximum_risk"], "total_usage_gb": row["total_usage_gb"],
                "block_count": row["block_count"] or 0, "review_count": row["review_count"] or 0,
            })


def refresh_analytics_cache(database_url: str) -> dict:
    """Refresh every precomputed analytics table (offer catalog/stats,
    kpi snapshot, subscriber summary, window snapshots) in the right
    order. Call this after any bulk data change -- see run_ingestion
    below and scripts/load_subscribers_daily.py."""
    counts = refresh_offer_catalog(database_url)
    refresh_kpi_snapshot(database_url)
    counts["subscriber_summary"] = refresh_subscriber_summary(database_url)
    refresh_window_snapshots(database_url)
    return counts


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
    refresh_analytics_cache(database_url)

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
