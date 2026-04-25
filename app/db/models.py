from datetime import datetime
from sqlalchemy import (
    Boolean, BigInteger, Column, Date, DateTime, Float,
    ForeignKey, Integer, String, Text, UniqueConstraint,
)
from app.database import Base


class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    rule_type = Column(String(50), nullable=False)
    scope = Column(String(30), nullable=False, default="account")
    scope_id = Column(String(200), nullable=True)
    conditions = Column(Text, nullable=False, default="[]")
    action = Column(Text, nullable=False, default="{}")
    schedule_cron = Column(String(50), nullable=True)
    priority = Column(Integer, default=10)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(80), nullable=True)


class JobRun(Base):
    __tablename__ = "job_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_name = Column(String(80), nullable=False)
    status = Column(String(20), nullable=False, default="running")
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    rules_evaluated = Column(Integer, default=0)
    actions_taken = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    error_summary = Column(Text, nullable=True)
    triggered_by = Column(String(30), default="scheduler")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_run_id = Column(Integer, ForeignKey("job_runs.id"), nullable=True)
    rule_id = Column(Integer, ForeignKey("automation_rules.id"), nullable=True)
    entity_type = Column(String(30), nullable=False)
    entity_resource = Column(String(200), nullable=False)
    action_taken = Column(String(200), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)


class PerformanceSnapshot(Base):
    __tablename__ = "performance_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, nullable=False)
    entity_type = Column(String(30), nullable=False)
    entity_id = Column(String(200), nullable=False)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    cost_micros = Column(BigInteger, default=0)
    conversions = Column(Float, default=0.0)
    ctr = Column(Float, default=0.0)
    avg_cpc_micros = Column(BigInteger, default=0)
    cpa_micros = Column(BigInteger, default=0)
    roas = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("snapshot_date", "entity_type", "entity_id"),
    )


class ReportCache(Base):
    __tablename__ = "report_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_type = Column(String(50), nullable=False)
    report_date = Column(Date, nullable=False)
    payload = Column(Text, nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("report_type", "report_date"),)


class CampaignCreationBatch(Base):
    __tablename__ = "campaign_creation_batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_type = Column(String(20), nullable=False)
    source_ref = Column(String(500), nullable=False)
    total_rows = Column(Integer, nullable=False)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    status = Column(String(20), default="pending")
    results = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)


class BudgetMonthlyCap(Base):
    __tablename__ = "budget_monthly_caps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_resource = Column(String(200), nullable=False)
    month_year = Column(String(7), nullable=False)
    cap_micros = Column(BigInteger, nullable=False)
    spent_micros = Column(BigInteger, default=0)
    is_paused_by_cap = Column(Boolean, default=False)
    last_checked_at = Column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("campaign_resource", "month_year"),)


class AlertHistory(Base):
    __tablename__ = "alert_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_type = Column(String(50), nullable=False)
    channel = Column(String(20), nullable=False)
    subject = Column(String(200), nullable=False)
    body_preview = Column(Text, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
    success = Column(Boolean, nullable=False)


class SearchTermSnapshot(Base):
    __tablename__ = "search_term_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, nullable=False)
    search_term = Column(String(500), nullable=False)
    ad_group_resource = Column(String(200), nullable=False)
    ad_group_name = Column(String(200), nullable=True)
    campaign_resource = Column(String(200), nullable=False)
    campaign_name = Column(String(200), nullable=True)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    cost_micros = Column(BigInteger, default=0)
    conversions = Column(Float, default=0.0)
    ctr = Column(Float, default=0.0)
    avg_cpc_micros = Column(BigInteger, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("snapshot_date", "search_term", "ad_group_resource"),)


class NegativeKeywordAdded(Base):
    __tablename__ = "negative_keywords_added"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword_text = Column(String(500), nullable=False)
    match_type = Column(String(20), default="BROAD")
    campaign_resource = Column(String(200), nullable=False)
    campaign_name = Column(String(200), nullable=True)
    reason = Column(String(200), nullable=True)
    clicks_wasted = Column(Integer, default=0)
    cost_wasted_micros = Column(BigInteger, default=0)
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("keyword_text", "campaign_resource"),)


class PromotedKeyword(Base):
    __tablename__ = "promoted_keywords"

    id = Column(Integer, primary_key=True, autoincrement=True)
    search_term = Column(String(500), nullable=False)
    ad_group_resource = Column(String(200), nullable=False)
    ad_group_name = Column(String(200), nullable=True)
    campaign_name = Column(String(200), nullable=True)
    conversions = Column(Float, default=0.0)
    clicks = Column(Integer, default=0)
    cost_micros = Column(BigInteger, default=0)
    criterion_resource = Column(String(200), nullable=True)
    promoted_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("search_term", "ad_group_resource"),)


class QualityScoreHistory(Base):
    __tablename__ = "quality_score_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, nullable=False)
    criterion_resource = Column(String(200), nullable=False)
    keyword_text = Column(String(500), nullable=False)
    match_type = Column(String(20), nullable=True)
    quality_score = Column(Integer, nullable=True)
    creative_quality = Column(String(30), nullable=True)
    landing_page_quality = Column(String(30), nullable=True)
    expected_ctr = Column(String(30), nullable=True)
    cpc_bid_micros = Column(BigInteger, default=0)
    clicks = Column(Integer, default=0)
    cost_micros = Column(BigInteger, default=0)
    ad_group_name = Column(String(200), nullable=True)
    campaign_name = Column(String(200), nullable=True)
    campaign_resource = Column(String(200), nullable=True)
    auto_paused = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("snapshot_date", "criterion_resource"),)


class MLBidPrediction(Base):
    __tablename__ = "ml_bid_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    criterion_resource = Column(String(200), nullable=False)
    keyword_text = Column(String(500), nullable=False)
    campaign_name = Column(String(200), nullable=True)
    current_bid_micros = Column(BigInteger, default=0)
    predicted_bid_micros = Column(BigInteger, default=0)
    predicted_cpa = Column(Float, default=0.0)
    confidence = Column(Float, default=0.0)
    action_taken = Column(String(50), nullable=True)
    model_version = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
