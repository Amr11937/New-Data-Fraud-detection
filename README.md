# FraudVision AI

Telecom fraud-risk dashboard. Subscriber usage is analysed **daily** (there is no
real-time detection): each subscriber/day is scored by an Isolation Forest model plus a
calibrated rule engine, combined into a risk score and an ALLOW / REVIEW / BLOCK decision.

Backend: one long-running FastAPI service on Postgres (RDS). Frontend: React + Vite + MUI +
ECharts, served by the same container. Originally the PCRF dashboard, merged with the
Broadband FMS ensemble -- see `MIGRATION_NOTES.md` for what was merged and verified.

## Layout

```
backend/    FastAPI + Postgres + rule engine + ensemble + ingest worker + scheduler
frontend/   React + Vite + MUI + ECharts dashboard (SLT-style light blue/green theme)
deploy/     redeploy.sh -- build, push and roll out to AWS ECS
```

## What the app shows

- **Executive summary** -- date-range filter, summary cards, last 7 / 30 day windows,
  daily risk + session trend, and a decisions-by-day graph (allow / review / block subscribers).
- **Subscribers** -- searchable, paginated list filtered by date, decision and risk score
  range (min / max); CSV and PDF export. Clicking a row opens the subscriber detail:
  usage tiles (download / upload etc.), offer / packages for each date, and risk score
  and duration graphs across all days.
- **Risk analytics** -- rule trigger statistics and offer / package distribution.
- **System health** -- database status, model version, active rules, latest data date.
- **Demask** -- batch-convert masked subscriber IDs back to originals, either with a
  mapping file or a decryption method. **Input and output files are parquet**, not CSV.

The login page is a front-end-only gate (no real authentication -- see `DEPLOYMENT.md`,
"Known gaps").

## Quick start (local)

1. **Database**: point `DATABASE_URL` at Postgres (the live RDS instance or a local copy)
   and make sure the tables exist (`backend/sql/schema.sql`, then the `migration_*.sql`
   files in order).

2. **Backend**:
   ```bash
   cd backend
   cp .env.example .env   # fill in DATABASE_URL (and ENCRYPTION_KEY for Demask)
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```
   The trained model artifacts are in `backend/app/artifacts/`.

3. **Frontend** (separate terminal):
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Open `http://localhost:5173/dashboard`. Vite proxies `/api/*` to port 8000
   (see `vite.config.ts`). Any username / password signs in.

## Loading data

Pre-aggregated, ML-scored parquet files (columns: `session_date, account_num,
subscriber_id, sessions_per_day, daily_usage_gb, ..., ratio, risk_score_0_100,
anomaly_rank`) are added with:

```bash
cd backend
export DATABASE_URL='postgresql+psycopg2://USER:PASS@HOST:5432/DB'
python scripts/load_scored_parquet.py --input path/to/final_output.parquet
```

It streams the file in batches, computes rule / ensemble scores and the decision for each
row, appends them, and refreshes the cached dashboard tables. It first deletes any existing
rows in the file's date range, so re-running after an interruption is safe. Use
`--skip-refresh` to skip the cache rebuild.

Other scripts in `backend/scripts/`:

- `load_subscribers_daily.py` -- older one-off loader (supports `--truncate`); leaves the
  decision columns empty, so run `backfill_ensemble_scores.py` afterwards.
- `backfill_ensemble_scores.py` -- fills rule / ml / final score and decision for rows
  that lack them.
- `ingest_daily_dataset.py` -- raw session-level file -> aggregate -> score -> insert.
- `calibrate_rules.py` -- recalibrate `app/config/rules.yaml` thresholds against real data.

**Note:** the production RDS instance is private. To load data from a PC, temporarily allow
your IP in the `pcrf-fms-rds-sg` security group (and set the instance publicly accessible),
run the loader, then revert both.

## Production build and deploy

```bash
cd frontend && npm run build
cp -r dist/* ../backend/frontend_dist/     # then delete stale hashed files in frontend_dist/assets
bash deploy/redeploy.sh                    # needs Docker Desktop running + AWS CLI configured
```

`redeploy.sh` builds the image, pushes it to ECR, registers a new ECS task definition and
rolls the service onto it. The single image serves the API and the built frontend and runs
the S3 ingest poller and daily-report scheduler in-process.

The ECS service starts the new task before stopping the old one (max 200% / min healthy
100%). A task needs ~3 GB, so the Auto Scaling Group must briefly have **two** servers:
set `pcrf-fms-asg` desired capacity to 2 before deploying (it is not scaled automatically).
Watch the rollout until it reports `COMPLETED`; if a task is stuck stopping, rebooting the
EC2 instance clears it.

See `DEPLOYMENT.md` for the AWS resources, live URL and known gaps (no HTTPS, no real
authentication, single-instance setup).

## Notes

- `backend/app/routers/ws.py` (WebSocket alerts) is still present but unused: the UI no
  longer shows live alerts or connection status.
- Pinned parquet support: `pyarrow` is in `backend/requirements.txt` (used by Demask).
