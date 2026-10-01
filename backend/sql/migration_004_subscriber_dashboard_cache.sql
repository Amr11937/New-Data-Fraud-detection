-- Precomputed per-subscriber summary: latest record + history length +
-- max risk score, one row per subscriber_id. Fixes two things at 4.5M+
-- rows: (1) GET /api/subscribers was running an unconditional full-table
-- `GROUP BY subscriber_id` just to compute history_days on EVERY request,
-- filtered or not; (2) its default (no date filter) view did a full
-- `DISTINCT ON (subscriber_id) ... ORDER BY session_date DESC` sort over
-- the whole table. Both now read/join this table instead. Also used by
-- GET /api/analytics/risk-distribution (max_risk_score_0_100) instead of
-- a live MAX(...) GROUP BY over subscribers_daily.
CREATE TABLE IF NOT EXISTS subscriber_summary (
    subscriber_id            TEXT PRIMARY KEY,
    account_num              TEXT,
    latest_session_date      DATE NOT NULL,
    latest_risk_score_0_100  DOUBLE PRECISION NOT NULL,
    latest_sessions_per_day  BIGINT,
    latest_daily_usage_gb    DOUBLE PRECISION,
    latest_rule_score        DOUBLE PRECISION,
    latest_ml_score          DOUBLE PRECISION,
    latest_final_score       DOUBLE PRECISION,
    latest_decision          TEXT,
    latest_triggered_rules   TEXT,
    history_days             BIGINT NOT NULL,
    max_risk_score_0_100     DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_subscriber_summary_final_score
    ON subscriber_summary ((COALESCE(latest_final_score, latest_risk_score_0_100 / 100.0)) DESC);

-- Precomputed GET /api/analytics/windows ("Last 7 days" / "Last 30 days"
-- cards on Executive Summary). Those windows, relative to MAX(session_date),
-- can cover nearly the entire table when real data is clustered in a short
-- span (as it currently is), making the live COUNT(DISTINCT subscriber_id)
-- version as expensive as the old unfiltered /api/kpis query was.
CREATE TABLE IF NOT EXISTS window_snapshot (
    label              TEXT PRIMARY KEY,
    date_from          DATE NOT NULL,
    date_to            DATE NOT NULL,
    as_of_date         DATE NOT NULL,
    days_with_data     BIGINT NOT NULL,
    total_subscribers  BIGINT NOT NULL,
    total_sessions     BIGINT NOT NULL,
    average_risk       DOUBLE PRECISION NOT NULL,
    maximum_risk       DOUBLE PRECISION NOT NULL,
    total_usage_gb     DOUBLE PRECISION NOT NULL,
    block_count        BIGINT NOT NULL,
    review_count       BIGINT NOT NULL
);

-- Speeds the 7x `triggered_rules LIKE '%rule_id%'` scans in
-- GET /api/analytics/rule-statistics (no index previously supported
-- pattern matching on this column), for both filtered and unfiltered
-- calls -- same trigram-index technique already used for subscriber_id
-- and account_num search in sql/schema.sql.
CREATE INDEX IF NOT EXISTS idx_subscribers_daily_triggered_rules_trgm
    ON subscribers_daily USING gin (triggered_rules gin_trgm_ops);
