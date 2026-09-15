-- PCRF dashboard schema. This is the exact table the FastAPI backend
-- queries. Your load-to-Postgres script (loading from the 615,027-row
-- parquet) needs to produce a table matching this shape.

CREATE TABLE IF NOT EXISTS subscribers_daily (
    id                          BIGSERIAL PRIMARY KEY,
    session_date                DATE            NOT NULL,
    account_num                 TEXT,
    subscriber_id               TEXT            NOT NULL,
    sessions_per_day            BIGINT          NOT NULL,
    daily_usage_gb               DOUBLE PRECISION NOT NULL,
    average_session_usage_gb     DOUBLE PRECISION,
    total_duration_minutes       DOUBLE PRECISION,
    average_session_duration_minutes DOUBLE PRECISION,
    total_input_gb               DOUBLE PRECISION,
    total_output_gb              DOUBLE PRECISION,
    offer_count                  BIGINT,
    offer_name                   TEXT,
    ratio                        DOUBLE PRECISION,
    risk_score_0_100             DOUBLE PRECISION NOT NULL,
    anomaly_rank                 BIGINT
);

-- Indexes for the dashboard's actual query patterns:
--  - filter by risk range, sorted by risk descending (the default list view)
--  - filter by session_date
--  - search by subscriber_id / account_num (prefix/substring)
--  - fetch one subscriber's full history (subscriber detail panel)
CREATE INDEX IF NOT EXISTS idx_subscribers_daily_risk
    ON subscribers_daily (risk_score_0_100 DESC);

CREATE INDEX IF NOT EXISTS idx_subscribers_daily_date
    ON subscribers_daily (session_date);

CREATE INDEX IF NOT EXISTS idx_subscribers_daily_subscriber
    ON subscribers_daily (subscriber_id);

CREATE INDEX IF NOT EXISTS idx_subscribers_daily_account
    ON subscribers_daily (account_num);

-- Trigram index makes ILIKE '%partial%' search fast at 615k+ rows.
-- Requires: CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_subscribers_daily_subscriber_trgm
    ON subscribers_daily USING gin (subscriber_id gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_subscribers_daily_account_trgm
    ON subscribers_daily USING gin (account_num gin_trgm_ops);
