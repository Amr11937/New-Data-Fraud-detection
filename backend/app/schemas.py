from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

# 5-tier banding for the ML-only risk_score_0_100, kept for backward
# compatibility with anything still reading that field directly.
RISK_THRESHOLDS = {
    "critical": 90.0,
    "high": 70.0,
    "medium": 40.0,
    "low": 20.0,
}


def risk_level_5tier(score: float) -> str:
    if score >= RISK_THRESHOLDS["critical"]:
        return "Critical"
    if score >= RISK_THRESHOLDS["high"]:
        return "High"
    if score >= RISK_THRESHOLDS["medium"]:
        return "Medium"
    if score >= RISK_THRESHOLDS["low"]:
        return "Low"
    return "Normal"


# ---------- Scoring ----------

class ScoreRequest(BaseModel):
    sessions_per_day: Optional[float] = None
    daily_usage_gb: Optional[float] = None
    average_session_usage_gb: Optional[float] = None
    total_duration_minutes: Optional[float] = None
    average_session_duration_minutes: Optional[float] = None
    total_input_gb: Optional[float] = None
    total_output_gb: Optional[float] = None
    offer_count: Optional[float] = None
    offer_name: Optional[str] = None
    Ratio: Optional[float] = Field(
        default=None,
        description="If omitted, computed server-side as total_input_gb / total_output_gb.",
    )


class ScoreResponse(BaseModel):
    risk_score_0_100: float
    risk_level: str
    anomaly_score: float
    features_used: dict
    # --- added by the merge ---
    rule_score: float
    ml_score: float
    final_score: float
    decision: str
    triggered_rules: list[str]


# ---------- Subscribers ----------

class SubscriberRow(BaseModel):
    session_date: date
    account_num: Optional[str]
    subscriber_id: str
    risk_score_0_100: float
    risk_level: str
    sessions_per_day: int
    daily_usage_gb: float
    history_days: int
    # --- added by the merge ---
    rule_score: Optional[float]
    ml_score: Optional[float]
    final_score: Optional[float]
    decision: Optional[str]
    triggered_rules: list[str] = []

    class Config:
        from_attributes = True


class SubscriberListResponse(BaseModel):
    items: list[SubscriberRow]
    total: int
    page: int
    page_size: int
    total_pages: int


class SubscriberDetailPoint(BaseModel):
    session_date: date
    total_input_gb: Optional[float]
    total_output_gb: Optional[float]
    risk_score_0_100: float
    final_score: Optional[float]
    decision: Optional[str]


class SubscriberDetail(BaseModel):
    subscriber_id: str
    account_num: Optional[str]
    latest_session_date: date
    maximum_risk_score: float
    average_risk_score: float
    risk_level: str
    sessions_per_day: int
    daily_usage_gb: float
    average_session_usage_gb: Optional[float]
    total_duration_minutes: Optional[float]
    average_session_duration_minutes: Optional[float]
    total_input_gb: Optional[float]
    total_output_gb: Optional[float]
    offer_name: Optional[str]
    history_days: int
    history: list[SubscriberDetailPoint]
    # --- added by the merge ---
    latest_decision: Optional[str]
    latest_final_score: Optional[float]
    triggered_rules_latest: list[str] = []


# ---------- Dashboard / KPIs ----------

class KpiResponse(BaseModel):
    total_subscribers: int
    total_packages: int
    total_sessions: int
    total_upload_gb: float
    total_download_gb: float
    total_usage_gb: float
    average_risk: float
    maximum_risk: float
    active_days: int
    sessions_per_day: float
    # --- added by the merge ---
    block_count: int
    review_count: int
    allow_count: int


class DailyPoint(BaseModel):
    date: date
    total_sessions: int
    average_risk: float
    average_download_gb: Optional[float]
    average_upload_gb: Optional[float]
    average_total_usage_gb: Optional[float]
    total_duration_minutes: Optional[float] = None
    block_count: int = 0
    review_count: int = 0


class RiskBand(BaseModel):
    label: str
    count: int
    percentage: float


class PackageStat(BaseModel):
    name: str
    value: float
    percentage: float


class PackageStatsResponse(BaseModel):
    distribution: list[PackageStat]
    usage: list[PackageStat]
    usage_is_approximate: bool


class WindowSummary(BaseModel):
    label: str
    date_from: date
    date_to: date
    days_with_data: int
    total_subscribers: int
    total_sessions: int
    average_risk: float
    maximum_risk: float
    total_usage_gb: float
    block_count: int = 0
    review_count: int = 0


class AnalyticsWindowsResponse(BaseModel):
    as_of_date: date
    last_7_days: WindowSummary
    last_30_days: WindowSummary


# ---------- Rule statistics (added by the merge) ----------

class RuleTriggerStat(BaseModel):
    rule_id: str
    feature: str
    upper_limit: float
    points: int
    trigger_count: int
    trigger_rate: float  # trigger_count / total rows in range


class RuleStatisticsResponse(BaseModel):
    date_from: Optional[date]
    date_to: Optional[date]
    total_rows: int
    block_count: int
    review_count: int
    allow_count: int
    rules: list[RuleTriggerStat]


# ---------- System health (added by the merge) ----------

class SystemHealthResponse(BaseModel):
    database: str
    model_version: str
    rule_engine_active_rules: int
    websocket_connections: int
    latest_session_date: Optional[date]
