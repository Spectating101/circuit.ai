"""
Database Models for Admin Dashboard

Models for:
- A/B testing experiments
- Feature flags
- System alerts
- Admin actions
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, JSON, ForeignKey, Index, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

Base = declarative_base()


class ExperimentStatus(enum.Enum):
    """A/B test experiment status."""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class VariantType(enum.Enum):
    """Experiment variant type."""
    CONTROL = "control"
    TREATMENT = "treatment"


class AlertSeverity(enum.Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(enum.Enum):
    """Alert status."""
    FIRING = "firing"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"


class Experiment(Base):
    """A/B testing experiments."""
    __tablename__ = 'experiments'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text)
    hypothesis = Column(Text)

    # Configuration
    feature_key = Column(String(255), nullable=False, index=True)
    traffic_percentage = Column(Float, default=100.0)  # % of users in experiment
    status = Column(Enum(ExperimentStatus), default=ExperimentStatus.DRAFT, nullable=False, index=True)

    # Targeting
    targeting_rules = Column(JSON, default={})  # User targeting criteria
    exclude_users = Column(JSON, default=[])  # User IDs to exclude

    # Metrics
    primary_metric = Column(String(255))
    secondary_metrics = Column(JSON, default=[])
    minimum_sample_size = Column(Integer, default=100)

    # Results
    winner_variant_id = Column(String(36))
    statistical_significance = Column(Float)  # p-value
    confidence_level = Column(Float)  # %

    # Timing
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    duration_days = Column(Integer)

    # Metadata
    created_by = Column(String(36), ForeignKey('users.id'))
    tags = Column(JSON, default=[])

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    variants = relationship("ExperimentVariant", back_populates="experiment", cascade="all, delete-orphan")
    assignments = relationship("ExperimentAssignment", back_populates="experiment", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_exp_status_start', 'status', 'start_date'),
    )


class ExperimentVariant(Base):
    """Experiment variants (control and treatments)."""
    __tablename__ = 'experiment_variants'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    experiment_id = Column(String(36), ForeignKey('experiments.id', ondelete='CASCADE'), nullable=False, index=True)

    # Variant details
    name = Column(String(255), nullable=False)
    description = Column(Text)
    variant_type = Column(Enum(VariantType), nullable=False)
    traffic_allocation = Column(Float, default=50.0)  # % of experiment traffic

    # Configuration
    config = Column(JSON, default={})  # Variant-specific config

    # Metrics
    total_users = Column(Integer, default=0)
    conversion_count = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)

    # Statistical metrics
    mean_value = Column(Float, default=0.0)
    std_deviation = Column(Float, default=0.0)
    confidence_interval = Column(JSON, default={})  # {lower, upper}

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    experiment = relationship("Experiment", back_populates="variants")

    __table_args__ = (
        Index('ix_variant_exp_type', 'experiment_id', 'variant_type'),
    )


class ExperimentAssignment(Base):
    """User assignments to experiment variants."""
    __tablename__ = 'experiment_assignments'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    experiment_id = Column(String(36), ForeignKey('experiments.id', ondelete='CASCADE'), nullable=False, index=True)
    variant_id = Column(String(36), ForeignKey('experiment_variants.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, index=True)

    # Assignment details
    assigned_at = Column(DateTime, default=datetime.utcnow)
    exposure_count = Column(Integer, default=0)  # Times user saw variant
    first_exposure_at = Column(DateTime)
    last_exposure_at = Column(DateTime)

    # Conversion tracking
    converted = Column(Boolean, default=False)
    converted_at = Column(DateTime)
    conversion_value = Column(Float)

    # Metadata
    user_properties = Column(JSON, default={})  # User properties at assignment time

    # Relationships
    experiment = relationship("Experiment", back_populates="assignments")

    __table_args__ = (
        Index('ix_assignment_user_exp', 'user_id', 'experiment_id'),
        Index('ix_assignment_variant', 'variant_id', 'assigned_at'),
    )


class FeatureFlag(Base):
    """Feature flag management."""
    __tablename__ = 'feature_flags'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Status
    enabled = Column(Boolean, default=False, nullable=False, index=True)

    # Rollout
    rollout_percentage = Column(Float, default=0.0)  # Gradual rollout
    targeting_rules = Column(JSON, default={})  # User targeting

    # Value (for multivariate flags)
    value_type = Column(String(50), default="boolean")  # boolean, string, number, json
    default_value = Column(JSON)
    variations = Column(JSON, default={})  # Named variations

    # Environment
    environment = Column(String(50), default="production", index=True)

    # Metadata
    tags = Column(JSON, default=[])
    owner_id = Column(String(36), ForeignKey('users.id'))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('ix_flag_env_enabled', 'environment', 'enabled'),
    )


class SystemAlert(Base):
    """System alerts and incidents."""
    __tablename__ = 'system_alerts'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    alert_name = Column(String(255), nullable=False, index=True)
    alert_source = Column(String(100), index=True)  # prometheus, custom, external

    # Alert details
    severity = Column(Enum(AlertSeverity), nullable=False, index=True)
    status = Column(Enum(AlertStatus), default=AlertStatus.FIRING, nullable=False, index=True)
    message = Column(Text, nullable=False)
    description = Column(Text)

    # Context
    labels = Column(JSON, default={})  # Alert labels (service, endpoint, etc.)
    annotations = Column(JSON, default={})  # Additional context
    metric_value = Column(Float)  # Triggering metric value
    threshold = Column(Float)  # Alert threshold

    # Timing
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime)
    acknowledged_at = Column(DateTime)
    duration_seconds = Column(Integer)

    # Assignment
    acknowledged_by = Column(String(36), ForeignKey('users.id'))
    assigned_to = Column(String(36), ForeignKey('users.id'))

    # Actions taken
    actions = Column(JSON, default=[])  # List of remediation actions
    resolution_notes = Column(Text)

    # Notification
    notification_sent = Column(Boolean, default=False)
    notification_channels = Column(JSON, default=[])  # email, slack, pagerduty

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('ix_alert_status_severity', 'status', 'severity'),
        Index('ix_alert_started', 'started_at'),
    )


class AdminAction(Base):
    """Admin action audit log."""
    __tablename__ = 'admin_actions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    admin_id = Column(String(36), ForeignKey('users.id'), nullable=False, index=True)

    # Action details
    action_type = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(100))
    resource_id = Column(String(36))
    description = Column(Text)

    # Changes
    changes = Column(JSON, default={})  # Before/after values
    affected_users = Column(JSON, default=[])  # User IDs affected

    # Context
    reason = Column(Text)
    ip_address = Column(String(45))
    user_agent = Column(String(512))

    # Result
    success = Column(Boolean, default=True)
    error_message = Column(Text)

    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index('ix_admin_action_type_time', 'action_type', 'timestamp'),
        Index('ix_admin_user_time', 'admin_id', 'timestamp'),
    )


class SystemHealth(Base):
    """System health snapshots."""
    __tablename__ = 'system_health'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Overall status
    status = Column(String(20), default="healthy")  # healthy, degraded, down

    # Service statuses
    api_status = Column(String(20))
    database_status = Column(String(20))
    redis_status = Column(String(20))
    ml_service_status = Column(String(20))

    # Metrics
    cpu_usage_percent = Column(Float)
    memory_usage_percent = Column(Float)
    disk_usage_percent = Column(Float)
    active_connections = Column(Integer)
    request_rate = Column(Float)  # req/s
    error_rate = Column(Float)  # %
    avg_response_time_ms = Column(Float)

    # Database metrics
    db_connections = Column(Integer)
    db_slow_queries = Column(Integer)

    # Queue metrics
    queue_depth = Column(Integer)
    queue_processing_rate = Column(Float)

    # Additional metrics
    metrics = Column(JSON, default={})

    __table_args__ = (
        Index('ix_health_timestamp', 'timestamp'),
    )
