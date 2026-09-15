FROM python:3.12-slim

WORKDIR /app

# duckdb / psycopg2 need these at build time
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY sql ./sql

# The React build output (frontend/dist) gets copied here by the deploy
# script/CI step -- see MIGRATION_NOTES.md. main.py serves it as a static
# SPA if present, and falls back to API-only mode if it's missing.
COPY frontend_dist ./frontend_dist

EXPOSE 8000

# Single long-running process: API + ingest poller + report scheduler
# all run inside this one uvicorn worker (see app/main.py lifespan).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
