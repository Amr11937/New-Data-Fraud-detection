from datetime import date as date_type
from math import ceil
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from ..db import get_session
from ..schemas import (
    SubscriberDetail,
    SubscriberDetailPoint,
    SubscriberListResponse,
    SubscriberRow,
    risk_level_5tier,
)

router = APIRouter(prefix="/api", tags=["subscribers"])


def _split_rules(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [r.strip() for r in value.split(",") if r.strip()]


@router.get("/subscribers", response_model=SubscriberListResponse)
def list_subscribers(
    min_risk: float = Query(0, ge=0, le=100),
    max_risk: float = Query(100, ge=0, le=100),
    decision: Optional[str] = Query(None, description="Filter: ALLOW, REVIEW, or BLOCK"),
    date: Optional[date_type] = Query(None, description="Deprecated: use date_from/date_to instead."),
    date_from: Optional[date_type] = Query(None, description="Inclusive start date"),
    date_to: Optional[date_type] = Query(None, description="Inclusive end date"),
    search: Optional[str] = Query(None, description="Matches subscriber_id or account_num, partial"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
) -> SubscriberListResponse:
    offset = (page - 1) * page_size

    if date is not None:
        date_from = date_from or date
        date_to = date_to or date

    if date_from is not None or date_to is not None:
        base_cte = """
            SELECT subscriber_id, account_num, session_date, risk_score_0_100,
                   sessions_per_day, daily_usage_gb, rule_score, ml_score,
                   final_score, decision, triggered_rules
            FROM subscribers_daily
            WHERE (:date_from IS NULL OR session_date >= :date_from)
              AND (:date_to IS NULL OR session_date <= :date_to)
        """
    else:
        base_cte = """
            SELECT DISTINCT ON (subscriber_id)
                   subscriber_id, account_num, session_date, risk_score_0_100,
                   sessions_per_day, daily_usage_gb, rule_score, ml_score,
                   final_score, decision, triggered_rules
            FROM subscribers_daily
            ORDER BY subscriber_id, session_date DESC
        """

    where_clauses = ["risk_score_0_100 >= :min_risk", "risk_score_0_100 <= :max_risk"]
    params = {"min_risk": min_risk, "max_risk": max_risk, "date_from": date_from, "date_to": date_to}
    if search:
        where_clauses.append("(subscriber_id ILIKE :search OR account_num ILIKE :search)")
        params["search"] = f"%{search}%"
    if decision:
        where_clauses.append("decision = :decision")
        params["decision"] = decision.upper()
    where_sql = " AND ".join(where_clauses)

    count_sql = text(f"WITH base AS ({base_cte}) SELECT COUNT(*) FROM base WHERE {where_sql}")

    page_sql = text(f"""
        WITH base AS ({base_cte}),
        filtered AS (SELECT * FROM base WHERE {where_sql}),
        with_history AS (
            SELECT f.*, h.history_days
            FROM filtered f
            JOIN (
                SELECT subscriber_id, COUNT(DISTINCT session_date) AS history_days
                FROM subscribers_daily
                GROUP BY subscriber_id
            ) h ON h.subscriber_id = f.subscriber_id
        )
        SELECT * FROM with_history
        ORDER BY COALESCE(final_score, risk_score_0_100 / 100.0) DESC, subscriber_id ASC
        LIMIT :limit OFFSET :offset
    """)

    with get_session() as session:
        total = session.execute(count_sql, params).scalar_one()
        rows = session.execute(page_sql, {**params, "limit": page_size, "offset": offset}).mappings().all()

    items = [
        SubscriberRow(
            session_date=row["session_date"],
            account_num=row["account_num"],
            subscriber_id=row["subscriber_id"],
            risk_score_0_100=row["risk_score_0_100"],
            risk_level=risk_level_5tier(row["risk_score_0_100"]),
            sessions_per_day=row["sessions_per_day"],
            daily_usage_gb=row["daily_usage_gb"],
            history_days=row["history_days"],
            rule_score=row["rule_score"],
            ml_score=row["ml_score"],
            final_score=row["final_score"],
            decision=row["decision"],
            triggered_rules=_split_rules(row["triggered_rules"]),
        )
        for row in rows
    ]

    return SubscriberListResponse(
        items=items, total=total, page=page, page_size=page_size, total_pages=max(1, ceil(total / page_size))
    )


@router.get("/subscribers/{subscriber_id}", response_model=SubscriberDetail)
def get_subscriber_detail(subscriber_id: str) -> SubscriberDetail:
    history_sql = text("""
        SELECT session_date, account_num, sessions_per_day, daily_usage_gb,
               average_session_usage_gb, total_duration_minutes,
               average_session_duration_minutes, total_input_gb, total_output_gb,
               offer_name, risk_score_0_100, final_score, decision, triggered_rules
        FROM subscribers_daily
        WHERE subscriber_id = :subscriber_id
        ORDER BY session_date ASC
    """)

    with get_session() as session:
        rows = session.execute(history_sql, {"subscriber_id": subscriber_id}).mappings().all()

    if not rows:
        raise HTTPException(status_code=404, detail=f"Subscriber {subscriber_id!r} not found")

    latest = rows[-1]
    risk_scores = [r["risk_score_0_100"] for r in rows]

    return SubscriberDetail(
        subscriber_id=subscriber_id,
        account_num=latest["account_num"],
        latest_session_date=latest["session_date"],
        maximum_risk_score=max(risk_scores),
        average_risk_score=sum(risk_scores) / len(risk_scores),
        risk_level=risk_level_5tier(latest["risk_score_0_100"]),
        sessions_per_day=latest["sessions_per_day"],
        daily_usage_gb=latest["daily_usage_gb"],
        average_session_usage_gb=latest["average_session_usage_gb"],
        total_duration_minutes=latest["total_duration_minutes"],
        average_session_duration_minutes=latest["average_session_duration_minutes"],
        total_input_gb=latest["total_input_gb"],
        total_output_gb=latest["total_output_gb"],
        offer_name=latest["offer_name"],
        history_days=len(rows),
        latest_decision=latest["decision"],
        latest_final_score=latest["final_score"],
        triggered_rules_latest=_split_rules(latest["triggered_rules"]),
        history=[
            SubscriberDetailPoint(
                session_date=r["session_date"],
                total_input_gb=r["total_input_gb"],
                total_output_gb=r["total_output_gb"],
                risk_score_0_100=r["risk_score_0_100"],
                final_score=r["final_score"],
                decision=r["decision"],
            )
            for r in rows
        ],
    )
