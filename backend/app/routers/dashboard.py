from datetime import date as date_type, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import text

from ..db import get_session
from ..rules import load_rules
from ..schemas import (
    AnalyticsWindowsResponse,
    CalendarDateInfo,
    CalendarDatesResponse,
    DailyPoint,
    KpiResponse,
    PackageStat,
    PackageStatsResponse,
    RiskBand,
    RuleStatisticsResponse,
    RuleTriggerStat,
    SystemHealthResponse,
    WindowSummary,
)
from ..websocket_manager import ws_manager

router = APIRouter(prefix="/api", tags=["dashboard"])

_DATE_RANGE_SQL = "(:date_from IS NULL OR session_date >= :date_from) AND (:date_to IS NULL OR session_date <= :date_to)"


@router.get("/kpis", response_model=KpiResponse)
def get_kpis(
    date_from: Optional[date_type] = Query(None),
    date_to: Optional[date_type] = Query(None),
) -> KpiResponse:
    # The dashboard's default, unfiltered load hits this case -- serve the
    # precomputed snapshot (see app.ingest_core.refresh_kpi_snapshot)
    # instead of a full unindexed scan, which is 20s+ at 4.5M+ rows.
    # Date-filtered requests fall through to the live query below, which
    # uses idx_subscribers_daily_date and is cheap for real-world windows.
    if date_from is None and date_to is None:
        with get_session() as session:
            snap = session.execute(text("SELECT * FROM kpi_snapshot WHERE id = 1")).mappings().one_or_none()
        if snap is not None:
            active_days = int(snap["active_days"]) or 1
            total_sessions = int(snap["total_sessions"])
            return KpiResponse(
                total_records=int(snap["total_records"]),
                total_subscribers=int(snap["total_subscribers"]),
                total_packages=int(snap["total_packages"]),
                total_sessions=total_sessions,
                total_upload_gb=round(float(snap["total_upload_gb"]), 4),
                total_download_gb=round(float(snap["total_download_gb"]), 4),
                total_usage_gb=round(float(snap["total_usage_gb"]), 4),
                average_risk=round(float(snap["average_risk"]), 2),
                maximum_risk=round(float(snap["maximum_risk"]), 2),
                active_days=int(snap["active_days"]),
                sessions_per_day=round(total_sessions / active_days, 2),
                block_count=int(snap["block_count"] or 0),
                review_count=int(snap["review_count"] or 0),
                allow_count=int(snap["allow_count"] or 0),
            )

    params = {"date_from": date_from, "date_to": date_to}

    sql = text(f"""
        SELECT
            COUNT(*)                           AS total_records,
            COUNT(DISTINCT subscriber_id)      AS total_subscribers,
            COALESCE(SUM(sessions_per_day), 0) AS total_sessions,
            COALESCE(SUM(total_output_gb), 0)  AS total_upload_gb,
            COALESCE(SUM(total_input_gb), 0)   AS total_download_gb,
            COALESCE(SUM(daily_usage_gb), 0)   AS total_usage_gb,
            COALESCE(AVG(risk_score_0_100), 0) AS average_risk,
            COALESCE(MAX(risk_score_0_100), 0) AS maximum_risk,
            COUNT(DISTINCT session_date)       AS active_days,
            SUM(CASE WHEN decision = 'BLOCK' THEN 1 ELSE 0 END)  AS block_count,
            SUM(CASE WHEN decision = 'REVIEW' THEN 1 ELSE 0 END) AS review_count,
            SUM(CASE WHEN decision = 'ALLOW' THEN 1 ELSE 0 END)  AS allow_count
        FROM subscribers_daily
        WHERE {_DATE_RANGE_SQL}
    """)
    packages_sql = text(f"""
        WITH distinct_offers AS (
            SELECT DISTINCT offer_name
            FROM subscribers_daily
            WHERE offer_name IS NOT NULL AND offer_name <> '' AND {_DATE_RANGE_SQL}
        )
        SELECT COUNT(DISTINCT t.single_offer) AS total_packages
        FROM distinct_offers d
        JOIN offer_name_tokens t ON t.offer_name = d.offer_name
    """)

    with get_session() as session:
        row = session.execute(sql, params).mappings().one()
        total_packages = session.execute(packages_sql, params).scalar_one()

    active_days = int(row["active_days"]) or 1
    total_sessions = int(row["total_sessions"])
    return KpiResponse(
        total_records=int(row["total_records"]),
        total_subscribers=int(row["total_subscribers"]),
        total_packages=int(total_packages),
        total_sessions=total_sessions,
        total_upload_gb=round(float(row["total_upload_gb"]), 4),
        total_download_gb=round(float(row["total_download_gb"]), 4),
        total_usage_gb=round(float(row["total_usage_gb"]), 4),
        average_risk=round(float(row["average_risk"]), 2),
        maximum_risk=round(float(row["maximum_risk"]), 2),
        active_days=int(row["active_days"]),
        sessions_per_day=round(total_sessions / active_days, 2),
        block_count=int(row["block_count"] or 0),
        review_count=int(row["review_count"] or 0),
        allow_count=int(row["allow_count"] or 0),
    )


@router.get("/analytics/daily", response_model=list[DailyPoint])
def get_daily_trend(
    date_from: Optional[date_type] = Query(None),
    date_to: Optional[date_type] = Query(None),
) -> list[DailyPoint]:
    params = {"date_from": date_from, "date_to": date_to}
    sql = text(f"""
        SELECT
            session_date AS date,
            COUNT(*) AS total_sessions,
            AVG(risk_score_0_100) AS average_risk,
            AVG(total_input_gb) AS average_download_gb,
            AVG(total_output_gb) AS average_upload_gb,
            AVG(daily_usage_gb) AS average_total_usage_gb,
            SUM(total_duration_minutes) AS total_duration_minutes,
            SUM(CASE WHEN decision = 'BLOCK' THEN 1 ELSE 0 END)  AS block_count,
            SUM(CASE WHEN decision = 'REVIEW' THEN 1 ELSE 0 END) AS review_count
        FROM subscribers_daily
        WHERE {_DATE_RANGE_SQL}
        GROUP BY session_date
        ORDER BY session_date ASC
    """)
    with get_session() as session:
        rows = session.execute(sql, params).mappings().all()

    return [
        DailyPoint(
            date=r["date"],
            total_sessions=r["total_sessions"],
            average_risk=round(r["average_risk"], 2),
            average_download_gb=round(r["average_download_gb"], 4) if r["average_download_gb"] is not None else None,
            average_upload_gb=round(r["average_upload_gb"], 4) if r["average_upload_gb"] is not None else None,
            average_total_usage_gb=round(r["average_total_usage_gb"], 4) if r["average_total_usage_gb"] is not None else None,
            total_duration_minutes=round(r["total_duration_minutes"], 2) if r["total_duration_minutes"] is not None else None,
            block_count=int(r["block_count"] or 0),
            review_count=int(r["review_count"] or 0),
        )
        for r in rows
    ]


@router.get("/analytics/calendar-dates", response_model=CalendarDatesResponse)
def get_calendar_dates() -> CalendarDatesResponse:
    sql = text("""
        SELECT session_date AS date, COUNT(*) AS record_count
        FROM subscribers_daily
        GROUP BY session_date
        ORDER BY session_date
    """)
    with get_session() as session:
        rows = session.execute(sql).mappings().all()

    dates = [CalendarDateInfo(date=r["date"], record_count=int(r["record_count"])) for r in rows]
    return CalendarDatesResponse(dates=dates, total_records=sum(d.record_count for d in dates))


def _window_summary(session, label: str, date_from: date_type, date_to: date_type) -> WindowSummary:
    sql = text("""
        SELECT
            COUNT(DISTINCT subscriber_id)      AS total_subscribers,
            COALESCE(SUM(sessions_per_day), 0) AS total_sessions,
            COALESCE(AVG(risk_score_0_100), 0) AS average_risk,
            COALESCE(MAX(risk_score_0_100), 0) AS maximum_risk,
            COALESCE(SUM(daily_usage_gb), 0)   AS total_usage_gb,
            COUNT(DISTINCT session_date)       AS days_with_data,
            SUM(CASE WHEN decision = 'BLOCK' THEN 1 ELSE 0 END)  AS block_count,
            SUM(CASE WHEN decision = 'REVIEW' THEN 1 ELSE 0 END) AS review_count
        FROM subscribers_daily
        WHERE session_date >= :date_from AND session_date <= :date_to
    """)
    row = session.execute(sql, {"date_from": date_from, "date_to": date_to}).mappings().one()
    return WindowSummary(
        label=label,
        date_from=date_from,
        date_to=date_to,
        days_with_data=int(row["days_with_data"]),
        total_subscribers=int(row["total_subscribers"]),
        total_sessions=int(row["total_sessions"]),
        average_risk=round(float(row["average_risk"]), 2),
        maximum_risk=round(float(row["maximum_risk"]), 2),
        total_usage_gb=round(float(row["total_usage_gb"]), 4),
        block_count=int(row["block_count"] or 0),
        review_count=int(row["review_count"] or 0),
    )


def _window_from_snapshot(row, label: str) -> WindowSummary:
    return WindowSummary(
        label=label,
        date_from=row["date_from"],
        date_to=row["date_to"],
        days_with_data=int(row["days_with_data"]),
        total_subscribers=int(row["total_subscribers"]),
        total_sessions=int(row["total_sessions"]),
        average_risk=round(float(row["average_risk"]), 2),
        maximum_risk=round(float(row["maximum_risk"]), 2),
        total_usage_gb=round(float(row["total_usage_gb"]), 4),
        block_count=int(row["block_count"] or 0),
        review_count=int(row["review_count"] or 0),
    )


@router.get("/analytics/windows", response_model=AnalyticsWindowsResponse)
def get_analytics_windows() -> AnalyticsWindowsResponse:
    # Precomputed by app.ingest_core.refresh_window_snapshots at ingest
    # time (see sql/migration_004_subscriber_dashboard_cache.sql) -- these
    # windows, relative to MAX(session_date), can cover nearly the whole
    # table when real data is clustered in a short span, making the live
    # COUNT(DISTINCT subscriber_id) version too slow at 4.5M+ rows.
    with get_session() as session:
        snap_rows = session.execute(text("SELECT * FROM window_snapshot")).mappings().all()
        by_label = {r["label"]: r for r in snap_rows}

        if "last_7_days" in by_label and "last_30_days" in by_label:
            last_7_row = by_label["last_7_days"]
            return AnalyticsWindowsResponse(
                as_of_date=last_7_row["as_of_date"],
                last_7_days=_window_from_snapshot(last_7_row, "Last 7 days"),
                last_30_days=_window_from_snapshot(by_label["last_30_days"], "Last 30 days"),
            )

        # Fallback (snapshot not yet built, e.g. right after migration):
        # compute live, same as before.
        latest = session.execute(text("SELECT MAX(session_date) FROM subscribers_daily")).scalar_one()
        if latest is None:
            today = date_type.today()
            empty = WindowSummary(
                label="No data", date_from=today, date_to=today, days_with_data=0,
                total_subscribers=0, total_sessions=0, average_risk=0.0, maximum_risk=0.0, total_usage_gb=0.0,
            )
            return AnalyticsWindowsResponse(as_of_date=today, last_7_days=empty, last_30_days=empty)

        last_7 = _window_summary(session, "Last 7 days", latest - timedelta(days=6), latest)
        last_30 = _window_summary(session, "Last 30 days", latest - timedelta(days=29), latest)

    return AnalyticsWindowsResponse(as_of_date=latest, last_7_days=last_7, last_30_days=last_30)


@router.get("/analytics/risk-distribution", response_model=list[RiskBand])
def get_risk_distribution() -> list[RiskBand]:
    # subscriber_summary.max_risk_score_0_100 is precomputed by
    # app.ingest_core.refresh_subscriber_summary (see
    # sql/migration_004_subscriber_dashboard_cache.sql), so this bands
    # ~600k precomputed per-subscriber maxes instead of running
    # MAX(...) GROUP BY over the full 4.5M+ row table.
    sql = text("""
        WITH banded AS (
            SELECT
                CASE
                    WHEN max_risk_score_0_100 >= 90 THEN '90-100'
                    ELSE LPAD((FLOOR(max_risk_score_0_100 / 10) * 10)::text, 2, '0')
                         || '-' || (FLOOR(max_risk_score_0_100 / 10) * 10 + 9)::text
                END AS label,
                FLOOR(LEAST(max_risk_score_0_100, 99) / 10) AS band_order
            FROM subscriber_summary
        )
        SELECT label, band_order, COUNT(*) AS count
        FROM banded
        GROUP BY label, band_order
        ORDER BY band_order ASC
    """)
    with get_session() as session:
        rows = session.execute(sql).mappings().all()
        total = sum(r["count"] for r in rows) or 1

    return [RiskBand(label=r["label"], count=r["count"], percentage=round(r["count"] / total * 100, 4)) for r in rows]


@router.get("/analytics/packages", response_model=PackageStatsResponse)
def get_package_stats() -> PackageStatsResponse:
    # Precomputed by app.ingest_core.refresh_offer_catalog at ingest time
    # (see sql/migration_002_offer_catalog.sql) -- COUNT(DISTINCT
    # subscriber_id) GROUP BY offer is too expensive to run per-request
    # at this row count, and this endpoint has no date filter to narrow
    # it with anyway.
    stats_sql = text("SELECT single_offer, subscriber_count, usage_gb FROM offer_stats")

    with get_session() as session:
        stats_rows = session.execute(stats_sql).mappings().all()
        total_subscribers = session.execute(text("SELECT total_subscribers FROM kpi_snapshot WHERE id = 1")).scalar_one()

    dist_rows = sorted(
        [{"name": r["single_offer"], "count": r["subscriber_count"]} for r in stats_rows],
        key=lambda r: r["count"], reverse=True,
    )
    usage_rows = sorted(
        [{"name": r["single_offer"], "usage_gb": r["usage_gb"]} for r in stats_rows if r["usage_gb"] is not None],
        key=lambda r: r["usage_gb"], reverse=True,
    )

    total_usage = sum(float(r["usage_gb"] or 0) for r in usage_rows) or 1

    distribution = [
        PackageStat(
            name=r["name"],
            value=float(r["count"]),
            percentage=round(r["count"] / total_subscribers * 100, 4) if total_subscribers else 0.0,
        )
        for r in dist_rows
    ]
    usage = [
        PackageStat(
            name=r["name"],
            value=round(float(r["usage_gb"] or 0), 4),
            percentage=round(float(r["usage_gb"] or 0) / total_usage * 100, 4),
        )
        for r in usage_rows
    ]
    return PackageStatsResponse(distribution=distribution, usage=usage, usage_is_approximate=True)


@router.get("/analytics/rule-statistics", response_model=RuleStatisticsResponse)
def get_rule_statistics(
    date_from: Optional[date_type] = Query(None),
    date_to: Optional[date_type] = Query(None),
) -> RuleStatisticsResponse:
    """Trigger counts per rule. NOTE: true/false-positive rates aren't
    included -- that needs labeled ground-truth fraud data, which this
    dataset doesn't have. If/when confirmed fraud cases get labeled,
    add a `confirmed_fraud` column and extend this query."""
    cfg = load_rules()
    rule_ids = [r for r in cfg if r.startswith("rule_")]
    params = {"date_from": date_from, "date_to": date_to}

    with get_session() as session:
        # The unfiltered case (dashboard default) reads the precomputed
        # kpi_snapshot instead of re-running this full-table scan -- same
        # values, already computed by app.ingest_core.refresh_kpi_snapshot.
        if date_from is None and date_to is None:
            snap = session.execute(
                text("SELECT total_records, block_count, review_count, allow_count FROM kpi_snapshot WHERE id = 1")
            ).mappings().one_or_none()
        else:
            snap = None

        if snap is not None:
            totals = snap
            total_rows = int(snap["total_records"])
        else:
            totals_sql = text(f"""
                SELECT
                    COUNT(*) AS total_rows,
                    SUM(CASE WHEN decision = 'BLOCK' THEN 1 ELSE 0 END)  AS block_count,
                    SUM(CASE WHEN decision = 'REVIEW' THEN 1 ELSE 0 END) AS review_count,
                    SUM(CASE WHEN decision = 'ALLOW' THEN 1 ELSE 0 END)  AS allow_count
                FROM subscribers_daily
                WHERE {_DATE_RANGE_SQL}
            """)
            totals = session.execute(totals_sql, params).mappings().one()
            total_rows = int(totals["total_rows"] or 0)

        rule_stats = []
        for rule_id in rule_ids:
            rule = cfg[rule_id]
            # Sped up by idx_subscribers_daily_triggered_rules_trgm
            # (sql/migration_004_subscriber_dashboard_cache.sql) --
            # previously an unindexed LIKE '%...%' scan of the full table.
            count_sql = text(f"""
                SELECT COUNT(*) FROM subscribers_daily
                WHERE {_DATE_RANGE_SQL} AND triggered_rules LIKE :pattern
            """)
            count = session.execute(count_sql, {**params, "pattern": f"%{rule_id}%"}).scalar_one()
            rule_stats.append(
                RuleTriggerStat(
                    rule_id=rule_id,
                    feature=rule["feature"],
                    upper_limit=rule["upper_limit"],
                    points=rule["points"],
                    trigger_count=int(count),
                    trigger_rate=round(count / total_rows, 4) if total_rows else 0.0,
                )
            )

    return RuleStatisticsResponse(
        date_from=date_from,
        date_to=date_to,
        total_rows=total_rows,
        block_count=int(totals["block_count"] or 0),
        review_count=int(totals["review_count"] or 0),
        allow_count=int(totals["allow_count"] or 0),
        rules=rule_stats,
    )


@router.get("/system-health", response_model=SystemHealthResponse)
def get_system_health() -> SystemHealthResponse:
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
            latest = session.execute(text("SELECT MAX(session_date) FROM subscribers_daily")).scalar_one()
        db_status = "connected"
    except Exception:
        db_status = "unreachable"
        latest = None

    cfg = load_rules()
    active_rules = len([r for r in cfg if r.startswith("rule_")])

    return SystemHealthResponse(
        database=db_status,
        model_version="isolation_forest_v1",
        rule_engine_active_rules=active_rules,
        websocket_connections=ws_manager.connection_count,
        latest_session_date=latest,
    )
