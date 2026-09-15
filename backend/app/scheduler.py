"""
Replaces the old daily_report_handler.py Lambda + EventBridge Scheduler
rule with an in-process APScheduler job, following the same pattern
Broadband FMS used for its background daemon: one long-running process
owns its own scheduling instead of relying on an external trigger.
"""
from __future__ import annotations

import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .report_service import run_daily_report

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _run_daily_report_job() -> None:
    try:
        result = run_daily_report()
        logger.info("Daily report job finished: %s", result)
    except Exception:
        logger.exception("Daily report job failed")


def start() -> AsyncIOScheduler:
    global _scheduler
    hour = int(os.environ.get("DAILY_REPORT_HOUR_UTC", "10"))
    minute = int(os.environ.get("DAILY_REPORT_MINUTE_UTC", "30"))

    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        _run_daily_report_job,
        CronTrigger(hour=hour, minute=minute),
        id="daily_risk_report",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Report scheduler started -- daily job at %02d:%02d UTC", hour, minute)
    return _scheduler


def stop() -> None:
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
