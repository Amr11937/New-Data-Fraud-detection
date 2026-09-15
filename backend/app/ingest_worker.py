"""
Background ingestion task. Replaces app/ingest_handler.py (the old
S3-ObjectCreated Lambda) with an async loop inside this long-running
process -- the same pattern Broadband FMS used for its
AutoTransactionMonitor daemon, applied to S3 instead of MongoDB.

Polls s3://INGEST_S3_BUCKET/INGEST_S3_RAW_PREFIX every
INGEST_POLL_INTERVAL_SECONDS. For each new file: downloads it,
aggregates + scores it (app/ingest_core.py), moves it to
INGEST_S3_PROCESSED_PREFIX so it isn't re-ingested next poll, and
broadcasts a WebSocket alert for every row scored REVIEW or BLOCK.

Trade-off vs. the old S3-event Lambda: this adds up to
INGEST_POLL_INTERVAL_SECONDS of latency between a file landing and it
being ingested, in exchange for one simpler deployable instead of a
separate Lambda + event notification config. Given the ~weekly ingest
cadence noted in the original daily_report_handler.py, that latency is
immaterial here. If sub-minute ingestion latency ever matters, swap
the polling loop for an SQS queue fed by the same S3 event
notification instead of re-introducing a separate Lambda.
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import urllib.parse

import boto3

from .ingest_core import run_ingestion
from .websocket_manager import ws_manager

logger = logging.getLogger(__name__)

BUCKET = os.environ.get("INGEST_S3_BUCKET", "")
RAW_PREFIX = os.environ.get("INGEST_S3_RAW_PREFIX", "raw/")
PROCESSED_PREFIX = os.environ.get("INGEST_S3_PROCESSED_PREFIX", "processed/")
POLL_INTERVAL = int(os.environ.get("INGEST_POLL_INTERVAL_SECONDS", "300"))
DATABASE_URL = os.environ["DATABASE_URL"]

_stop_event = asyncio.Event()


def _list_raw_keys(s3) -> list[str]:
    if not BUCKET:
        return []
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=RAW_PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key != RAW_PREFIX and not key.endswith("/"):
                keys.append(key)
    return keys


def _process_one_key(s3, key: str) -> dict:
    suffix = ".parquet" if key.endswith(".parquet") else ".csv"
    with tempfile.NamedTemporaryFile(suffix=suffix, dir="/tmp", delete=False) as tmp:
        local_path = tmp.name

    s3.download_file(BUCKET, key, local_path)
    result = run_ingestion(local_path, DATABASE_URL)
    logger.info("Ingested %d rows from s3://%s/%s (dates: %s)", result["rows_ingested"], BUCKET, key, result["dates"])

    processed_key = key.replace(RAW_PREFIX, PROCESSED_PREFIX, 1) if key.startswith(RAW_PREFIX) else f"{PROCESSED_PREFIX}{key}"
    s3.copy_object(Bucket=BUCKET, CopySource={"Bucket": BUCKET, "Key": key}, Key=processed_key)
    s3.delete_object(Bucket=BUCKET, Key=key)
    return result


def _poll_once_sync() -> list[dict]:
    """All blocking boto3/DuckDB/Postgres work, run off the event loop."""
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION"))
    results = []
    for key in _list_raw_keys(s3):
        key = urllib.parse.unquote_plus(key)
        try:
            results.append(_process_one_key(s3, key))
        except Exception:
            logger.exception("Ingestion failed for s3://%s/%s -- left in place for retry", BUCKET, key)
    return results


async def _broadcast_alerts(results: list[dict]) -> None:
    for result in results:
        for alert in result.get("alerts", []):
            await ws_manager.broadcast({"type": "fraud_event", **alert})


async def run_forever() -> None:
    if not BUCKET:
        logger.warning("INGEST_S3_BUCKET is not set -- ingestion worker will not poll S3.")
    logger.info("Ingestion worker started. Polling every %ds.", POLL_INTERVAL)

    while not _stop_event.is_set():
        try:
            results = await asyncio.to_thread(_poll_once_sync)
            await _broadcast_alerts(results)
        except Exception:
            logger.exception("Ingestion poll cycle failed")

        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=POLL_INTERVAL)
        except asyncio.TimeoutError:
            pass  # normal: just means it's time to poll again


def stop() -> None:
    _stop_event.set()
