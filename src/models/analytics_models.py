"""
Database Models for Analytics & Tracking

Models for:
- Event tracking
- User behavior analytics
- Feature usage stats
- Funnel analysis
- Session tracking
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, JSON, ForeignKey, Index, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()


class Event(Base):
    """Analytics event tracking."""
    __tablename__ = 'events'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, index=True)
    session_id = Column(String(36), nullable=False, index=True)
    event_name = Column(String(255), nullable=False, index=True)
    properties = Column(JSON, default={})
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Computed fields for analytics
    page_url = Column(String(1024))
    referrer = Column(String(1024))
    user_agent = Column(String(512))
    ip_address = Column(String(45))
    country = Column(String(2))
    city = Column(String(255))

    # Indexes for common queries
    __table_args__ = (
        Index('ix_events_user_timestamp', 'user_id', 'timestamp'),
        Index('ix_events_name_timestamp', 'event_name', 'timestamp'),
        Index('ix_events_session_timestamp', 'session_id', 'timestamp'),
    )


class UserSession(Base):
    """User session tracking."""
    __tablename__ = 'user_sessions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, index=True)
    session_start = Column(DateTime, nullable=False, default=datetime.utcnow)
    session_end = Column(DateTime)
    duration_seconds = Column(Integer)
    page_views = Column(Integer, default=0)
    events_count = Column(Integer, default=0)

    # Device/browser info
    device_type = Column(String(50))  # mobile, tablet, desktop
    browser = Column(String(100))
    os = Column(String(100))

    # Location
    country = Column(String(2))
    city = Column(String(255))

    # Engagement metrics
    bounce = Column(Boolean, default=False)  # Single page session

    __table_args__ = (
        Index('ix_sessions_user_start', 'user_id', 'session_start'),
    )


class FeatureUsageStat(Base):
    """Feature usage statistics (aggregated daily)."""
    __tablename__ = 'feature_usage_stats'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    feature_name = Column(String(255), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)

    # Metrics
    total_uses = Column(Integer, default=0)
    unique_users = Column(Integer, default=0)
    avg_uses_per_user = Column(Float, default=0.0)
    total_users = Column(Integer, default=0)  # For adoption rate

    __table_args__ = (
        Index('ix_feature_stats_name_date', 'feature_name', 'date'),
    )


class FunnelStep(Base):
    """Funnel step definitions and tracking."""
    __tablename__ = 'funnel_steps'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    funnel_name = Column(String(255), nullable=False, index=True)
    step_name = Column(String(255), nullable=False)
    step_order = Column(Integer, nullable=False)
    event_name = Column(String(255), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_funnel_name_order', 'funnel_name', 'step_order'),
    )


class FunnelConversion(Base):
    """Funnel conversion tracking (aggregated daily)."""
    __tablename__ = 'funnel_conversions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    funnel_name = Column(String(255), nullable=False, index=True)
    step_name = Column(String(255), nullable=False)
    date = Column(DateTime, nullable=False, index=True)

    # Metrics
    users_entered = Column(Integer, default=0)
    users_completed = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)

    __table_args__ = (
        Index('ix_funnel_conv_name_date', 'funnel_name', 'date'),
    )


class UserBehaviorMetric(Base):
    """User behavior metrics (computed periodically)."""
    __tablename__ = 'user_behavior_metrics'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), unique=True, nullable=False, index=True)

    # Session metrics
    session_count = Column(Integer, default=0)
    total_time_spent_minutes = Column(Float, default=0.0)
    avg_session_duration_minutes = Column(Float, default=0.0)

    # Analysis metrics
    total_analyses = Column(Integer, default=0)
    avg_analyses_per_session = Column(Float, default=0.0)

    # Engagement
    last_active = Column(DateTime, default=datetime.utcnow)
    days_since_signup = Column(Integer, default=0)
    days_active = Column(Integer, default=0)

    # Feature usage
    favorite_features = Column(JSON, default=[])  # List of most used features

    # Churn prediction
    churn_risk_score = Column(Float, default=0.0)  # 0-1
    churn_risk_level = Column(String(20))  # low, medium, high

    # Timestamps
    computed_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CohortAnalysis(Base):
    """Cohort analysis data."""
    __tablename__ = 'cohort_analysis'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cohort_month = Column(DateTime, nullable=False, index=True)  # User signup month
    age_months = Column(Integer, nullable=False)  # Months since signup

    # Metrics
    cohort_size = Column(Integer, default=0)
    active_users = Column(Integer, default=0)
    retention_rate = Column(Float, default=0.0)
    revenue = Column(Float, default=0.0)
    arpu = Column(Float, default=0.0)  # Average revenue per user

    # Computed
    computed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_cohort_month_age', 'cohort_month', 'age_months'),
    )


class UserLTV(Base):
    """User Lifetime Value calculations."""
    __tablename__ = 'user_ltv'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), unique=True, nullable=False, index=True)

    # LTV metrics
    ltv = Column(Float, default=0.0)
    avg_monthly_spend = Column(Float, default=0.0)
    predicted_lifetime_months = Column(Float, default=0.0)
    confidence = Column(Float, default=0.0)  # 0-1

    # Actual metrics
    total_revenue = Column(Float, default=0.0)
    months_active = Column(Integer, default=0)

    # Computed
    computed_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RevenueMetric(Base):
    """Revenue metrics (aggregated daily/monthly)."""
    __tablename__ = 'revenue_metrics'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    period_type = Column(String(20), nullable=False, index=True)  # day, week, month, year
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False)

    # Revenue breakdown
    total_revenue = Column(Float, default=0.0)
    new_revenue = Column(Float, default=0.0)  # From new customers
    expansion_revenue = Column(Float, default=0.0)  # Upgrades
    contraction_revenue = Column(Float, default=0.0)  # Downgrades
    churn_revenue = Column(Float, default=0.0)  # Lost

    # Recurring metrics
    mrr = Column(Float, default=0.0)  # Monthly Recurring Revenue
    arr = Column(Float, default=0.0)  # Annual Recurring Revenue

    # Customer metrics
    new_customers = Column(Integer, default=0)
    churned_customers = Column(Integer, default=0)
    total_customers = Column(Integer, default=0)

    # Calculated metrics
    net_revenue_retention = Column(Float, default=0.0)  # %
    gross_revenue_retention = Column(Float, default=0.0)  # %
    churn_rate = Column(Float, default=0.0)  # %

    # Computed
    computed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_revenue_type_start', 'period_type', 'period_start'),
    )


class ActivityLog(Base):
    """Audit log of all user activities."""
    __tablename__ = 'activity_logs'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey('organizations.id'), index=True)

    # Activity details
    action = Column(String(255), nullable=False, index=True)
    resource_type = Column(String(100), index=True)
    resource_id = Column(String(36))
    description = Column(Text)

    # Context
    ip_address = Column(String(45))
    user_agent = Column(String(512))
    metadata = Column(JSON, default={})

    # Result
    success = Column(Boolean, default=True)
    error_message = Column(Text)

    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index('ix_activity_user_timestamp', 'user_id', 'timestamp'),
        Index('ix_activity_org_timestamp', 'organization_id', 'timestamp'),
        Index('ix_activity_action_timestamp', 'action', 'timestamp'),
    )
