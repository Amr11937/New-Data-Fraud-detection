# PCRF Fraud Risk Dashboard -- merged with Broadband FMS

This is the merged system: PCRF's RDS Postgres data store and real
615k+ row model stayed as the source of truth; Broadband FMS's
weighted ensemble (rules + ML), WebSocket alerts, and React/MUI/ECharts
frontend were ported on top of it. The backend is now one long-running
FastAPI service (ECS/EC2, not Lambda) instead of three separate Lambda
containers.

**Both halves have been actually run and verified, not just written --
see MIGRATION_NOTES.md for exactly what was tested and what's still a
placeholder.**

## Layout

```
backend/    FastAPI + Postgres + rule engine + ensemble + ingest worker + scheduler
frontend/   React + Vite + MUI + ECharts dashboard
```

## Quick start (local)

1. **Database**: point `DATABASE_URL` at your existing PCRF RDS instance
   (or a local Postgres for testing), then run the merge migration:
   ```bash
   psql "$DATABASE_URL" -f backend/sql/migration_001_merge_ensemble.sql
   ```
   This only adds nullable columns -- safe against the live 615k-row table.
   To backfill ensemble scores for existing rows:
   ```bash
   cd backend && python scripts/backfill_ensemble_scores.py
   ```

2. **Backend**:
   ```bash
   cd backend
   cp .env.example .env   # fill in DATABASE_URL, INGEST_S3_BUCKET, SES vars
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```
   The trained Isolation Forest model artifacts are already included in
   `backend/app/artifacts/` -- no separate download needed.

3. **Frontend** (separate terminal):
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Open `http://localhost:5173/dashboard`. Vite proxies `/api/*` to the
   backend on port 8000 (see `vite.config.ts`).

4. **Recalibrate the rule engine** against real data before relying on
   it (see MIGRATION_NOTES.md -- the shipped `rules.yaml` thresholds
   are placeholders):
   ```bash
   cd backend && python scripts/calibrate_rules.py --percentile 95
   ```

## Production build

```bash
cd frontend && npm run build
cp -r dist/* ../backend/frontend_dist/
cd ../backend && docker build -t pcrf-fms .
```

The one Docker image serves the API and the SPA together, and runs the
ingest poller + daily report scheduler in-process (see `app/main.py`
lifespan). Deploy it to ECS or EC2 behind a load balancer, pointed at
the same RDS instance and S3 bucket PCRF already uses.
"# New-Data-Fraud-detection" 
