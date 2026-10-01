-- Precomputed all-time KPI snapshot for GET /api/kpis when called with no
-- date_from/date_to (the dashboard's default, unfiltered load -- the slow
-- path: a full unindexed scan of subscribers_daily for COUNT(DISTINCT
-- subscriber_id) + several SUM/AVG, 20s+ at 4.5M+ rows). Date-filtered
-- requests still compute live (narrower windows use idx_subscribers_daily_date
-- and are much cheaper). Refreshed by app.ingest_core.refresh_kpi_snapshot
-- after each data load, same as offer_stats (migration_002).
CREATE TABLE IF NOT EXISTS kpi_snapshot (
    id                 INTEGER PRIMARY KEY DEFAULT 1,
    total_records      BIGINT NOT NULL,
    total_subscribers  BIGINT NOT NULL,
    total_packages     BIGINT NOT NULL,
    total_sessions     BIGINT NOT NULL,
    total_upload_gb    DOUBLE PRECISION NOT NULL,
    total_download_gb  DOUBLE PRECISION NOT NULL,
    total_usage_gb     DOUBLE PRECISION NOT NULL,
    average_risk       DOUBLE PRECISION NOT NULL,
    maximum_risk       DOUBLE PRECISION NOT NULL,
    active_days        BIGINT NOT NULL,
    block_count        BIGINT NOT NULL,
    review_count       BIGINT NOT NULL,
    allow_count        BIGINT NOT NULL,
    refreshed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT kpi_snapshot_singleton CHECK (id = 1)
);
