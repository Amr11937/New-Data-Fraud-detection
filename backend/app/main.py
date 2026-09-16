import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import ingest_worker, scheduler
from .model_service import model_service  # noqa: F401 -- import triggers artifact load at startup
from .routers import dashboard, reports, scoring, subscribers, ws

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pcrf_fms")

_ingest_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ingest_task

    logger.info("Isolation Forest model loaded (artifacts/isolation_forest_model.pkl)")

    _ingest_task = asyncio.create_task(ingest_worker.run_forever())
    scheduler.start()
    logger.info("Startup complete: ingest worker + report scheduler running in-process.")

    yield

    ingest_worker.stop()
    scheduler.stop()
    if _ingest_task is not None:
        _ingest_task.cancel()
    logger.info("Shutdown complete.")


app = FastAPI(title="PCRF Fraud Risk API (merged)", version="2.0.0", lifespan=lifespan)

allowed_origins = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(scoring.router)
app.include_router(subscribers.router)
app.include_router(dashboard.router)
app.include_router(reports.router)
app.include_router(ws.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# --- Serve the React SPA if it's been built alongside the backend ---
# (frontend/dist copied into ./frontend_dist -- see Dockerfile and
# MIGRATION_NOTES.md). If it's missing, the API still runs fine on its
# own, e.g. during local backend-only development.
FRONTEND_DIST = Path(__file__).parent.parent / "frontend_dist"
_frontend_built = (FRONTEND_DIST / "index.html").is_file()
if _frontend_built and (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        index = FRONTEND_DIST / "index.html"
        return FileResponse(index)
else:
    logger.warning("frontend_dist is empty -- running in API-only mode. See MIGRATION_NOTES.md.")


# Local dev entrypoint: `python -m app.main` (production uses the
# Dockerfile's `uvicorn app.main:app` CMD instead).
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
