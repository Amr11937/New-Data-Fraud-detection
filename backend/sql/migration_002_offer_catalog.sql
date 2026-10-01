-- Precomputed offer_name -> individual offer token lookup. offer_name is
-- a comma-joined combination string (e.g. "VOD_8GB_PUL, VOD_8GB_PDL"); at
-- 4.5M+ rows, exploding it with unnest(string_to_array(...)) on every row
-- for every /api/analytics/packages or /api/kpis request is too slow
-- (tens of seconds). There are only ~128k distinct offer_name combos
-- (and ~600 distinct individual tokens), so this table is built once per
-- data load (see app/ingest_core.refresh_offer_catalog) and queries join
-- against it instead of calling unnest live.
CREATE TABLE IF NOT EXISTS offer_name_tokens (
    offer_name   TEXT NOT NULL,
    single_offer TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_offer_name_tokens_offer_name
    ON offer_name_tokens (offer_name);

-- Precomputed final stats for GET /api/analytics/packages (no date
-- filter in that endpoint, so this can be fully precomputed rather than
-- aggregated per-request). COUNT(DISTINCT subscriber_id) GROUP BY offer
-- is expensive regardless of how the offer join is done (sort/hash
-- dedup over the full joined set), so it's computed once per data
-- refresh instead of once per request.
CREATE TABLE IF NOT EXISTS offer_stats (
    single_offer     TEXT PRIMARY KEY,
    subscriber_count BIGINT NOT NULL,
    usage_gb         DOUBLE PRECISION
);
