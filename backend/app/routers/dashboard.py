from datetime import date as date_type, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import text

from ..db import get_session
from ..rules import load_rules
from ..schemas import (
    AnalyticsWindowsResponse,
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
    params = {"date_from": date_from, "date_to": date_to}

    sql = text(f"""
        SELECT
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
        SELECT COUNT(DISTINCT single_offer) AS total_packages
        FROM subscribers_daily,
             LATERAL unnest(string_to_array(offer_name, ', ')) AS single_offer
        WHERE offer_name IS NOT NULL AND offer_name <> '' AND {_DATE_RANGE_SQL}
    """)

    with get_session() as session:
        row = session.execute(sql, params).mappings().one()
        total_packages = session.execute(packages_sql, params).scalar_one()

    active_days = int(row["active_days"]) or 1
    total_sessions = int(row["total_sessions"])
    return KpiResponse(
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


@router.get("/analytics/windows", response_model=AnalyticsWindowsResponse)
def get_analytics_windows() -> AnalyticsWindowsResponse:
    with get_session() as session:
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
    sql = text("""
        WITH per_subscriber AS (
            SELECT subscriber_id, MAX(risk_score_0_100) AS max_risk
            FROM subscribers_daily
            GROUP BY subscriber_id
        ),
        banded AS (
            SELECT
                CASE
                    WHEN max_risk >= 90 THEN '90-100'
                    ELSE LPAD((FLOOR(max_risk / 10) * 10)::text, 2, '0')
                         || '-' || (FLOOR(max_risk / 10) * 10 + 9)::text
                END AS label,
                FLOOR(LEAST(max_risk, 99) / 10) AS band_order
            FROM per_subscriber
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
    distribution_sql = text("""
        SELECT single_offer AS name, COUNT(DISTINCT subscriber_id) AS count
        FROM subscribers_daily,
             LATERAL unnest(string_to_array(offer_name, ', ')) AS single_offer
        WHERE offer_name IS NOT NULL AND offer_name <> ''
        GROUP BY single_offer
        ORDER BY count DESC
    """)
    usage_sql = text("""
        SELECT single_offer AS name, SUM(daily_usage_gb / NULLIF(offer_count, 0)) AS usage_gb
        FROM subscribers_daily,
             LATERAL unnest(string_to_array(offer_name, ', ')) AS single_offer
        WHERE offer_name IS NOT NULL AND offer_name <> ''
        GROUP BY single_offer
        ORDER BY usage_gb DESC
    """)

    with get_session() as session:
        dist_rows = session.execute(distribution_sql).mappings().all()
        usage_rows = session.execute(usage_sql).mappings().all()
        total_subscribers = session.execute(text("SELECT COUNT(DISTINCT subscriber_id) FROM subscribers_daily")).scalar_one()

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

    totals_sql = text(f"""
        SELECT
            COUNT(*) AS total_rows,
            SUM(CASE WHEN decision = 'BLOCK' THEN 1 ELSE 0 END)  AS block_count,
            SUM(CASE WHEN decision = 'REVIEW' THEN 1 ELSE 0 END) AS review_count,
            SUM(CASE WHEN decision = 'ALLOW' THEN 1 ELSE 0 END)  AS allow_count
        FROM subscribers_daily
        WHERE {_DATE_RANGE_SQL}
    """)

    with get_session() as session:
        totals = session.execute(totals_sql, params).mappings().one()
        total_rows = int(totals["total_rows"] or 0)

        rule_stats = []
        for rule_id in rule_ids:
            rule = cfg[rule_id]
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
