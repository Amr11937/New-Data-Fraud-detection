# Migration notes -- what's real, what's a placeholder

## What was actually run and verified (not just written)

- **Full scoring pipeline end-to-end**, using the real trained model
  artifacts: `POST /api/score` with a synthetic heavy-usage profile
  correctly triggered 5 of 7 rules, ran the Isolation Forest, combined
  them through the ensemble, and returned `decision: BLOCK` with a
  sensible `final_score`. See the terminal output from the build
  session if you want to reproduce it.
- **App boot**, including the lifespan startup: the ingest worker task
  and the APScheduler daily-report job both start cleanly, and shut
  down cleanly, with no `DATABASE_URL` connection actually needed at
  import time (SQLAlchemy's `create_engine` doesn't connect eagerly).
- **`/api/health` and `/openapi.json`** both return 200 -- every
  Pydantic response model in every router is structurally valid.
- **Frontend**: `npm run build` completes with **zero TypeScript
  errors** against the real `tsc` compiler, and the resulting bundle is
  correctly served by the backend's SPA fallback route (verified: a
  client-side route like `/dashboard/subscribers` returns the built
  `index.html`, and `/api/health` keeps working alongside it).

None of this was tested against a real Postgres connection, a real S3
bucket, or real SES sending -- I don't have credentials for your AWS
account. Everything above the database layer is real; the database
layer itself is only syntax- and logic-verified, not connection-tested.

## Known placeholders -- fix these before trusting the system

1. **Rule thresholds in `backend/app/config/rules.yaml`** are flat 5x
   multiples of the medians in `feature_medians.json`, not real
   percentile cutoffs. Run `scripts/calibrate_rules.py` against your
   live table and replace the file with its output before relying on
   `decision` for anything operational. The `points` weighting per
   rule is untouched from Broadband's original judgment call --
   revisit once you see real trigger rates from
   `/api/analytics/rule-statistics`.

2. **`rule_05`** was repurposed from Broadband's "max single session
   usage" (which needs per-session data this daily-aggregated schema
   doesn't store) to a session-count burst rule instead. If per-session
   granularity ever gets added to the pipeline, the original rule could
   be restored.

3. **Rule statistics have no true/false-positive rates** -- Broadband's
   original `RuleBreakdownItem` type included `true_positives` /
   `false_positives`, which needs labeled ground-truth fraud outcomes.
   This dataset doesn't have that label, so `RuleStatisticsResponse`
   only reports trigger counts and rates. Add a `confirmed_fraud`
   column and extend `get_rule_statistics()` in `routers/dashboard.py`
   if/when labeled cases exist.

4. **Ingest latency**: the S3 poller (`app/ingest_worker.py`) checks
   every `INGEST_POLL_INTERVAL_SECONDS` (default 300s) instead of
   reacting to the S3 event instantly like the old Lambda did. Given
   the ~weekly ingest cadence noted in the original
   `daily_report_handler.py`, this is immaterial -- but if sub-minute
   latency ever matters, swap the polling loop for an SQS queue fed by
   the same S3 event notification.

5. **`INGEST_S3_BUCKET`, SES sender/recipients, and `DATABASE_URL`**
   are all unset placeholders in `.env.example` -- fill in your actual
   values before deploying.

## Frontend scope, vs. Broadband's original 7-page dashboard

Broadband's frontend assumed hourly-granularity data (`hourly_trend`,
peak-hour charts) that genuinely doesn't exist in PCRF's schema --
`subscribers_daily` is aggregated to one row per subscriber per day,
with no session-level timestamps retained after ingest. Rather than
fabricate hourly charts from data that isn't there, this build has 4
pages covering what's actually queryable:

- **Executive summary** -- KPIs, 7/30-day rolling windows, daily trend, risk distribution
- **Subscribers** -- filterable/paginated table, detail drawer, CSV + PDF export
- **Risk analytics** -- rule trigger statistics, offer/package distribution
- **System health** -- DB connectivity, model version, WebSocket connections, latest ingest date

If you want Broadband's Traffic Analytics (peak hours) or hourly Fraud
Overview pages specifically, that requires keeping session-level
records post-ingest instead of only the daily aggregate -- a schema
change, not just a frontend one.

## Files you still need to place by hand

- `backend/frontend_dist/` needs the frontend's `dist/` output copied
  in before `docker build` (see root README's "Production build"
  section) -- it's already done once in this delivered zip, but will
  need re-doing after any frontend changes.
