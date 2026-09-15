-- Adds the rule-engine + ensemble fields from the Broadband FMS merge
-- on top of the existing PCRF subscribers_daily table. Safe to run
-- against the live 615k+ row table -- all additions are nullable, so
-- existing rows just get NULLs until backfilled (see
-- scripts/backfill_ensemble_scores.py).

ALTER TABLE subscribers_daily
    ADD COLUMN IF NOT EXISTS rule_score       DOUBLE PRECISION,  -- 0-1, from the rule engine
    ADD COLUMN IF NOT EXISTS ml_score         DOUBLE PRECISION,  -- 0-1, = risk_score_0_100 / 100
    ADD COLUMN IF NOT EXISTS final_score       DOUBLE PRECISION,  -- 0-1, weighted ensemble output
    ADD COLUMN IF NOT EXISTS decision         TEXT,              -- 'ALLOW' | 'REVIEW' | 'BLOCK'
    ADD COLUMN IF NOT EXISTS triggered_rules   TEXT;              -- comma-joined rule ids, e.g. 'rule_01, rule_04'

CREATE INDEX IF NOT EXISTS idx_subscribers_daily_decision
    ON subscribers_daily (decision);

CREATE INDEX IF NOT EXISTS idx_subscribers_daily_final_score
    ON subscribers_daily (final_score DESC);
