"""
Database Models for Webhooks

Models for:
- Webhook registrations
- Webhook deliveries
- Delivery attempts
- Webhook events
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, JSON, ForeignKey, Index, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

Base = declarative_base()


class WebhookStatus(enum.Enum):
    """Webhook status enum."""
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class DeliveryStatus(enum.Enum):
    """Webhook delivery status."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class Webhook(Base):
    """Webhook registration."""
    __tablename__ = 'webhooks'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey('organizations.id'), index=True)

    # Webhook config
    url = Column(String(2048), nullable=False)
    secret = Column(String(255), nullable=False)  # For HMAC signatures
    description = Column(String(500))

    # Event filtering
    events = Column(JSON, default=[])  # List of event patterns to subscribe to
    event_filter = Column(JSON, default={})  # Additional filtering criteria

    # Status
    status = Column(Enum(WebhookStatus), default=WebhookStatus.ACTIVE, nullable=False, index=True)
    is_active = Column(Boolean, default=True, index=True)

    # Retry configuration
    max_retries = Column(Integer, default=3)
    retry_delay_seconds = Column(Integer, default=60)

    # Statistics
    total_deliveries = Column(Integer, default=0)
    successful_deliveries = Column(Integer, default=0)
    failed_deliveries = Column(Integer, default=0)
    last_delivery_at = Column(DateTime)
    last_success_at = Column(DateTime)
    last_failure_at = Column(DateTime)

    # Metadata
    metadata = Column(JSON, default={})

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    deliveries = relationship("WebhookDelivery", back_populates="webhook", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_webhooks_user_status', 'user_id', 'status'),
        Index('ix_webhooks_org_status', 'organization_id', 'status'),
    )


class WebhookDelivery(Base):
    """Webhook delivery record."""
    __tablename__ = 'webhook_deliveries'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    webhook_id = Column(String(36), ForeignKey('webhooks.id', ondelete='CASCADE'), nullable=False, index=True)

    # Event details
    event_type = Column(String(255), nullable=False, index=True)
    event_id = Column(String(36), index=True)
    payload = Column(JSON, nullable=False)

    # Delivery status
    status = Column(Enum(DeliveryStatus), default=DeliveryStatus.PENDING, nullable=False, index=True)
    attempts = Column(Integer, default=0)
    next_retry_at = Column(DateTime, index=True)

    # Response details
    response_status_code = Column(Integer)
    response_body = Column(Text)
    response_headers = Column(JSON, default={})
    error_message = Column(Text)

    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    delivered_at = Column(DateTime)
    duration_ms = Column(Integer)

    # Relationships
    webhook = relationship("Webhook", back_populates="deliveries")
    attempts_log = relationship("WebhookAttempt", back_populates="delivery", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_delivery_webhook_created', 'webhook_id', 'created_at'),
        Index('ix_delivery_status_created', 'status', 'created_at'),
        Index('ix_delivery_event_type', 'event_type', 'created_at'),
    )


class WebhookAttempt(Base):
    """Individual webhook delivery attempt."""
    __tablename__ = 'webhook_attempts'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    delivery_id = Column(String(36), ForeignKey('webhook_deliveries.id', ondelete='CASCADE'), nullable=False, index=True)

    # Attempt details
    attempt_number = Column(Integer, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    duration_ms = Column(Integer)

    # Request details
    request_url = Column(String(2048))
    request_headers = Column(JSON, default={})
    request_body = Column(Text)

    # Response details
    response_status_code = Column(Integer)
    response_body = Column(Text)
    response_headers = Column(JSON, default={})

    # Result
    success = Column(Boolean, default=False)
    error_message = Column(Text)
    error_type = Column(String(100))  # timeout, connection, http_error, etc.

    # Relationships
    delivery = relationship("WebhookDelivery", back_populates="attempts_log")

    __table_args__ = (
        Index('ix_attempt_delivery_number', 'delivery_id', 'attempt_number'),
    )


class WebhookEvent(Base):
    """Webhook event types registry."""
    __tablename__ = 'webhook_events'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(255), unique=True, nullable=False, index=True)
    category = Column(String(100), index=True)  # analysis, bom, user, subscription, etc.
    description = Column(Text)
    schema_version = Column(String(20), default="1.0")
    payload_schema = Column(JSON, default={})  # JSON Schema for validation

    # Stats
    total_triggered = Column(Integer, default=0)
    total_delivered = Column(Integer, default=0)

    # Status
    is_active = Column(Boolean, default=True)
    is_deprecated = Column(Boolean, default=False)
    deprecated_message = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('ix_event_category_active', 'category', 'is_active'),
    )


class WebhookSecret(Base):
    """Webhook secret rotation tracking."""
    __tablename__ = 'webhook_secrets'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    webhook_id = Column(String(36), ForeignKey('webhooks.id', ondelete='CASCADE'), nullable=False, index=True)

    # Secret details
    secret = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, index=True)

    # Rotation
    expires_at = Column(DateTime)
    rotated_at = Column(DateTime)
    rotation_reason = Column(String(255))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_secret_webhook_active', 'webhook_id', 'is_active'),
    )
