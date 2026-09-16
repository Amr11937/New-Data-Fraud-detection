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
- **Demask (subscriber ID recovery)**, ported from
  [chinthakadd7/Demask](https://github.com/chinthakadd7/Demask) and
  merged in under `/api/demask/*` + the "Demask" nav page instead of
  running as its own service:
  - `POST /api/demask/mapping` against Demask's own
    `sample_data/mapping_input.csv` + `mapping_lookup.csv` -- returned
    8 `MAPPED` / 2 `UNMAPPED` rows (matching the lookup CSV's actual
    coverage) with correct `X-Total-Records` / `X-Processed` /
    `X-Unprocessed` / `X-Errors` headers.
  - `POST /api/demask/encryption` against
    `sample_data/encryption_input.csv` with `demo_cipher` -- all 10
    `ENC_<id>_<tag>` tokens decrypted back to their original IDs.
  - `DemoCipherProvider` verified as a true round-trip (encrypt then
    decrypt returns the original value) directly in Python, not just
    against the demo token shortcut.
  - `FernetProvider` (real AES, via the `cryptography` package added
    to `requirements.txt`) verified directly against a locally
    generated throwaway Fernet key/token pair -- decrypts correctly.
  - `GET /api/demask/encryption/methods` correctly lists
    `demo_cipher`, `aes_token`, and `fernet`, with `configured: true`
    once `ENCRYPTION_KEY` is set.
  - A malformed request (missing input column) correctly returns
    `422` with a descriptive `detail` message.
  - `npm run dev` was **not** exercised interactively for the new
    `DemaskPage` (no browser in this environment) -- only the API
    layer and the production build/SPA-fallback were verified end to
    end. Manually click through both flows (mapping + encryption,
    including the progress bar and CSV download) before relying on
    the page.

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

6. **`ENCRYPTION_KEY` is unset in `.env.example`** -- Demask's
   endpoints work without it (mapping doesn't need it, and the demo
   token shortcut in `DemoCipherProvider.decrypt_value` handles the
   `ENC_<id>_<tag>` sample data regardless of key), but any real
   decryption needs a real key set. The Fernet key used above for
   testing was generated locally for this session
   (`Fernet.generate_key()`) and is not stored anywhere -- generate
   and set your own before using the `fernet` provider for anything
   real.

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
