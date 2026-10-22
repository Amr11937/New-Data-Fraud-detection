-- Per-package risk: one row per subscriber / day / package, with the
-- Isolation Forest's risk score for that package (from
-- pcrf_package_isolation_forest_results.parquet). Separate from
-- subscribers_daily (one row per subscriber / day) because the grain is
-- different -- appending these rows there would double count subscribers.
-- Loaded by scripts/load_package_risk.py.
CREATE TABLE IF NOT EXISTS subscriber_package_daily (
    id                               BIGSERIAL PRIMARY KEY,
    session_date                     DATE NOT NULL,
    account_num                      TEXT,
    subscriber_id                    TEXT NOT NULL,
    package_name                     TEXT NOT NULL,
    sessions_per_day                 BIGINT,
    download_gb                      DOUBLE PRECISION,
    upload_gb                        DOUBLE PRECISION,
    total_usage_gb                   DOUBLE PRECISION,
    total_duration_minutes           DOUBLE PRECISION,
    average_session_duration_minutes DOUBLE PRECISION,
    average_session_usage_gb         DOUBLE PRECISION,
    anomaly_score                    DOUBLE PRECISION,
    risk_score_0_100                 DOUBLE PRECISION NOT NULL,
    risk_level                       TEXT
);

CREATE INDEX IF NOT EXISTS idx_pkg_daily_subscriber ON subscriber_package_daily (subscriber_id);
CREATE INDEX IF NOT EXISTS idx_pkg_daily_date ON subscriber_package_daily (session_date);

-- Tiny per-(date, package) rollup (a few thousand rows) so the Risk analytics
-- package section can filter by date range without scanning millions of rows.
-- Rebuilt by scripts/load_package_risk.py after each load.
CREATE TABLE IF NOT EXISTS package_risk_daily (
    session_date  DATE NOT NULL,
    package_name  TEXT NOT NULL,
    row_count     BIGINT NOT NULL,
    risk_sum      DOUBLE PRECISION NOT NULL,
    risk_max      DOUBLE PRECISION NOT NULL,
    high_count    BIGINT NOT NULL,
    medium_count  BIGINT NOT NULL,
    low_count     BIGINT NOT NULL,
    PRIMARY KEY (session_date, package_name)
);
