from sqlalchemy import BigInteger, Column, Date, Float, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SubscriberDaily(Base):
    __tablename__ = "subscribers_daily"

    id = Column(BigInteger, primary_key=True)
    session_date = Column(Date, nullable=False)
    account_num = Column(String)
    subscriber_id = Column(String, nullable=False)
    sessions_per_day = Column(BigInteger, nullable=False)
    daily_usage_gb = Column(Float, nullable=False)
    average_session_usage_gb = Column(Float)
    total_duration_minutes = Column(Float)
    average_session_duration_minutes = Column(Float)
    total_input_gb = Column(Float)
    total_output_gb = Column(Float)
    offer_count = Column(Integer)
    offer_name = Column(String)
    ratio = Column(Float)
    risk_score_0_100 = Column(Float, nullable=False)
    anomaly_rank = Column(BigInteger)

    # --- added by the Broadband FMS merge (migration_001) ---
    rule_score = Column(Float)          # 0-1, rule engine output
    ml_score = Column(Float)            # 0-1, = risk_score_0_100 / 100
    final_score = Column(Float)         # 0-1, weighted ensemble output
    decision = Column(String)           # 'ALLOW' | 'REVIEW' | 'BLOCK'
    triggered_rules = Column(String)    # comma-joined rule ids
