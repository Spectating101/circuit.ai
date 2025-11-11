"""
Add analytics, webhooks, and admin tables

Revision ID: 002_analytics_webhooks_admin
Revises: 001_initial_migration
Create Date: 2025-11-11 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers
revision = '002_analytics_webhooks_admin'
down_revision = '001_initial_migration'
branch_labels = None
depends_on = None


def upgrade():
    """Create analytics, webhooks, and admin tables."""

    # ===== ANALYTICS TABLES =====

    # Events table
    op.create_table(
        'events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('session_id', sa.String(36), nullable=False, index=True),
        sa.Column('event_name', sa.String(255), nullable=False, index=True),
        sa.Column('properties', postgresql.JSONB, default={}),
        sa.Column('timestamp', sa.DateTime, nullable=False, index=True),
        sa.Column('page_url', sa.String(1024)),
        sa.Column('referrer', sa.String(1024)),
        sa.Column('user_agent', sa.String(512)),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('country', sa.String(2)),
        sa.Column('city', sa.String(255))
    )

    op.create_index('ix_events_user_timestamp', 'events', ['user_id', 'timestamp'])
    op.create_index('ix_events_name_timestamp', 'events', ['event_name', 'timestamp'])
    op.create_index('ix_events_session_timestamp', 'events', ['session_id', 'timestamp'])

    # User sessions table
    op.create_table(
        'user_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('session_start', sa.DateTime, nullable=False),
        sa.Column('session_end', sa.DateTime),
        sa.Column('duration_seconds', sa.Integer),
        sa.Column('page_views', sa.Integer, default=0),
        sa.Column('events_count', sa.Integer, default=0),
        sa.Column('device_type', sa.String(50)),
        sa.Column('browser', sa.String(100)),
        sa.Column('os', sa.String(100)),
        sa.Column('country', sa.String(2)),
        sa.Column('city', sa.String(255)),
        sa.Column('bounce', sa.Boolean, default=False)
    )

    op.create_index('ix_sessions_user_start', 'user_sessions', ['user_id', 'session_start'])

    # Feature usage stats table
    op.create_table(
        'feature_usage_stats',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('feature_name', sa.String(255), nullable=False, index=True),
        sa.Column('date', sa.DateTime, nullable=False, index=True),
        sa.Column('total_uses', sa.Integer, default=0),
        sa.Column('unique_users', sa.Integer, default=0),
        sa.Column('avg_uses_per_user', sa.Float, default=0.0),
        sa.Column('total_users', sa.Integer, default=0)
    )

    op.create_index('ix_feature_stats_name_date', 'feature_usage_stats', ['feature_name', 'date'])

    # User behavior metrics table
    op.create_table(
        'user_behavior_metrics',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), unique=True, nullable=False, index=True),
        sa.Column('session_count', sa.Integer, default=0),
        sa.Column('total_time_spent_minutes', sa.Float, default=0.0),
        sa.Column('avg_session_duration_minutes', sa.Float, default=0.0),
        sa.Column('total_analyses', sa.Integer, default=0),
        sa.Column('avg_analyses_per_session', sa.Float, default=0.0),
        sa.Column('last_active', sa.DateTime),
        sa.Column('days_since_signup', sa.Integer, default=0),
        sa.Column('days_active', sa.Integer, default=0),
        sa.Column('favorite_features', postgresql.JSONB, default=[]),
        sa.Column('churn_risk_score', sa.Float, default=0.0),
        sa.Column('churn_risk_level', sa.String(20)),
        sa.Column('computed_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime)
    )

    # Cohort analysis table
    op.create_table(
        'cohort_analysis',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('cohort_month', sa.DateTime, nullable=False, index=True),
        sa.Column('age_months', sa.Integer, nullable=False),
        sa.Column('cohort_size', sa.Integer, default=0),
        sa.Column('active_users', sa.Integer, default=0),
        sa.Column('retention_rate', sa.Float, default=0.0),
        sa.Column('revenue', sa.Float, default=0.0),
        sa.Column('arpu', sa.Float, default=0.0),
        sa.Column('computed_at', sa.DateTime)
    )

    op.create_index('ix_cohort_month_age', 'cohort_analysis', ['cohort_month', 'age_months'])

    # User LTV table
    op.create_table(
        'user_ltv',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), unique=True, nullable=False, index=True),
        sa.Column('ltv', sa.Float, default=0.0),
        sa.Column('avg_monthly_spend', sa.Float, default=0.0),
        sa.Column('predicted_lifetime_months', sa.Float, default=0.0),
        sa.Column('confidence', sa.Float, default=0.0),
        sa.Column('total_revenue', sa.Float, default=0.0),
        sa.Column('months_active', sa.Integer, default=0),
        sa.Column('computed_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime)
    )

    # Revenue metrics table
    op.create_table(
        'revenue_metrics',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('period_type', sa.String(20), nullable=False, index=True),
        sa.Column('period_start', sa.DateTime, nullable=False, index=True),
        sa.Column('period_end', sa.DateTime, nullable=False),
        sa.Column('total_revenue', sa.Float, default=0.0),
        sa.Column('new_revenue', sa.Float, default=0.0),
        sa.Column('expansion_revenue', sa.Float, default=0.0),
        sa.Column('contraction_revenue', sa.Float, default=0.0),
        sa.Column('churn_revenue', sa.Float, default=0.0),
        sa.Column('mrr', sa.Float, default=0.0),
        sa.Column('arr', sa.Float, default=0.0),
        sa.Column('new_customers', sa.Integer, default=0),
        sa.Column('churned_customers', sa.Integer, default=0),
        sa.Column('total_customers', sa.Integer, default=0),
        sa.Column('net_revenue_retention', sa.Float, default=0.0),
        sa.Column('gross_revenue_retention', sa.Float, default=0.0),
        sa.Column('churn_rate', sa.Float, default=0.0),
        sa.Column('computed_at', sa.DateTime)
    )

    op.create_index('ix_revenue_type_start', 'revenue_metrics', ['period_type', 'period_start'])

    # Activity logs table
    op.create_table(
        'activity_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id'), index=True),
        sa.Column('action', sa.String(255), nullable=False, index=True),
        sa.Column('resource_type', sa.String(100), index=True),
        sa.Column('resource_id', sa.String(36)),
        sa.Column('description', sa.Text),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.String(512)),
        sa.Column('metadata', postgresql.JSONB, default={}),
        sa.Column('success', sa.Boolean, default=True),
        sa.Column('error_message', sa.Text),
        sa.Column('timestamp', sa.DateTime, index=True)
    )

    op.create_index('ix_activity_user_timestamp', 'activity_logs', ['user_id', 'timestamp'])
    op.create_index('ix_activity_org_timestamp', 'activity_logs', ['organization_id', 'timestamp'])
    op.create_index('ix_activity_action_timestamp', 'activity_logs', ['action', 'timestamp'])

    # ===== WEBHOOK TABLES =====

    # Webhooks table
    op.create_table(
        'webhooks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id'), index=True),
        sa.Column('url', sa.String(2048), nullable=False),
        sa.Column('secret', sa.String(255), nullable=False),
        sa.Column('description', sa.String(500)),
        sa.Column('events', postgresql.JSONB, default=[]),
        sa.Column('event_filter', postgresql.JSONB, default={}),
        sa.Column('status', sa.String(20), nullable=False, index=True),
        sa.Column('is_active', sa.Boolean, default=True, index=True),
        sa.Column('max_retries', sa.Integer, default=3),
        sa.Column('retry_delay_seconds', sa.Integer, default=60),
        sa.Column('total_deliveries', sa.Integer, default=0),
        sa.Column('successful_deliveries', sa.Integer, default=0),
        sa.Column('failed_deliveries', sa.Integer, default=0),
        sa.Column('last_delivery_at', sa.DateTime),
        sa.Column('last_success_at', sa.DateTime),
        sa.Column('last_failure_at', sa.DateTime),
        sa.Column('metadata', postgresql.JSONB, default={}),
        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime)
    )

    op.create_index('ix_webhooks_user_status', 'webhooks', ['user_id', 'status'])
    op.create_index('ix_webhooks_org_status', 'webhooks', ['organization_id', 'status'])

    # Webhook deliveries table
    op.create_table(
        'webhook_deliveries',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('webhook_id', sa.String(36), sa.ForeignKey('webhooks.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('event_type', sa.String(255), nullable=False, index=True),
        sa.Column('event_id', sa.String(36), index=True),
        sa.Column('payload', postgresql.JSONB, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, index=True),
        sa.Column('attempts', sa.Integer, default=0),
        sa.Column('next_retry_at', sa.DateTime, index=True),
        sa.Column('response_status_code', sa.Integer),
        sa.Column('response_body', sa.Text),
        sa.Column('response_headers', postgresql.JSONB, default={}),
        sa.Column('error_message', sa.Text),
        sa.Column('created_at', sa.DateTime, index=True),
        sa.Column('delivered_at', sa.DateTime),
        sa.Column('duration_ms', sa.Integer)
    )

    op.create_index('ix_delivery_webhook_created', 'webhook_deliveries', ['webhook_id', 'created_at'])
    op.create_index('ix_delivery_status_created', 'webhook_deliveries', ['status', 'created_at'])
    op.create_index('ix_delivery_event_type', 'webhook_deliveries', ['event_type', 'created_at'])

    # Webhook attempts table
    op.create_table(
        'webhook_attempts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('delivery_id', sa.String(36), sa.ForeignKey('webhook_deliveries.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('attempt_number', sa.Integer, nullable=False),
        sa.Column('started_at', sa.DateTime),
        sa.Column('completed_at', sa.DateTime),
        sa.Column('duration_ms', sa.Integer),
        sa.Column('request_url', sa.String(2048)),
        sa.Column('request_headers', postgresql.JSONB, default={}),
        sa.Column('request_body', sa.Text),
        sa.Column('response_status_code', sa.Integer),
        sa.Column('response_body', sa.Text),
        sa.Column('response_headers', postgresql.JSONB, default={}),
        sa.Column('success', sa.Boolean, default=False),
        sa.Column('error_message', sa.Text),
        sa.Column('error_type', sa.String(100))
    )

    op.create_index('ix_attempt_delivery_number', 'webhook_attempts', ['delivery_id', 'attempt_number'])

    # Webhook events table
    op.create_table(
        'webhook_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('event_type', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('category', sa.String(100), index=True),
        sa.Column('description', sa.Text),
        sa.Column('schema_version', sa.String(20), default="1.0"),
        sa.Column('payload_schema', postgresql.JSONB, default={}),
        sa.Column('total_triggered', sa.Integer, default=0),
        sa.Column('total_delivered', sa.Integer, default=0),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('is_deprecated', sa.Boolean, default=False),
        sa.Column('deprecated_message', sa.Text),
        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime)
    )

    op.create_index('ix_event_category_active', 'webhook_events', ['category', 'is_active'])

    # ===== ADMIN TABLES =====

    # Experiments table (A/B testing)
    op.create_table(
        'experiments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('description', sa.Text),
        sa.Column('hypothesis', sa.Text),
        sa.Column('feature_key', sa.String(255), nullable=False, index=True),
        sa.Column('traffic_percentage', sa.Float, default=100.0),
        sa.Column('status', sa.String(20), nullable=False, index=True),
        sa.Column('targeting_rules', postgresql.JSONB, default={}),
        sa.Column('exclude_users', postgresql.JSONB, default=[]),
        sa.Column('primary_metric', sa.String(255)),
        sa.Column('secondary_metrics', postgresql.JSONB, default=[]),
        sa.Column('minimum_sample_size', sa.Integer, default=100),
        sa.Column('winner_variant_id', sa.String(36)),
        sa.Column('statistical_significance', sa.Float),
        sa.Column('confidence_level', sa.Float),
        sa.Column('start_date', sa.DateTime),
        sa.Column('end_date', sa.DateTime),
        sa.Column('duration_days', sa.Integer),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('tags', postgresql.JSONB, default=[]),
        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime)
    )

    op.create_index('ix_exp_status_start', 'experiments', ['status', 'start_date'])

    # Experiment variants table
    op.create_table(
        'experiment_variants',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('experiment_id', sa.String(36), sa.ForeignKey('experiments.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('variant_type', sa.String(20), nullable=False),
        sa.Column('traffic_allocation', sa.Float, default=50.0),
        sa.Column('config', postgresql.JSONB, default={}),
        sa.Column('total_users', sa.Integer, default=0),
        sa.Column('conversion_count', sa.Integer, default=0),
        sa.Column('conversion_rate', sa.Float, default=0.0),
        sa.Column('mean_value', sa.Float, default=0.0),
        sa.Column('std_deviation', sa.Float, default=0.0),
        sa.Column('confidence_interval', postgresql.JSONB, default={}),
        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime)
    )

    op.create_index('ix_variant_exp_type', 'experiment_variants', ['experiment_id', 'variant_type'])

    # Experiment assignments table
    op.create_table(
        'experiment_assignments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('experiment_id', sa.String(36), sa.ForeignKey('experiments.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('variant_id', sa.String(36), sa.ForeignKey('experiment_variants.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('assigned_at', sa.DateTime),
        sa.Column('exposure_count', sa.Integer, default=0),
        sa.Column('first_exposure_at', sa.DateTime),
        sa.Column('last_exposure_at', sa.DateTime),
        sa.Column('converted', sa.Boolean, default=False),
        sa.Column('converted_at', sa.DateTime),
        sa.Column('conversion_value', sa.Float),
        sa.Column('user_properties', postgresql.JSONB, default={})
    )

    op.create_index('ix_assignment_user_exp', 'experiment_assignments', ['user_id', 'experiment_id'])
    op.create_index('ix_assignment_variant', 'experiment_assignments', ['variant_id', 'assigned_at'])

    # Feature flags table
    op.create_table(
        'feature_flags',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('key', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('enabled', sa.Boolean, default=False, nullable=False, index=True),
        sa.Column('rollout_percentage', sa.Float, default=0.0),
        sa.Column('targeting_rules', postgresql.JSONB, default={}),
        sa.Column('value_type', sa.String(50), default="boolean"),
        sa.Column('default_value', postgresql.JSONB),
        sa.Column('variations', postgresql.JSONB, default={}),
        sa.Column('environment', sa.String(50), default="production", index=True),
        sa.Column('tags', postgresql.JSONB, default=[]),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime)
    )

    op.create_index('ix_flag_env_enabled', 'feature_flags', ['environment', 'enabled'])

    # System alerts table
    op.create_table(
        'system_alerts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('alert_name', sa.String(255), nullable=False, index=True),
        sa.Column('alert_source', sa.String(100), index=True),
        sa.Column('severity', sa.String(20), nullable=False, index=True),
        sa.Column('status', sa.String(20), nullable=False, index=True),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('labels', postgresql.JSONB, default={}),
        sa.Column('annotations', postgresql.JSONB, default={}),
        sa.Column('metric_value', sa.Float),
        sa.Column('threshold', sa.Float),
        sa.Column('started_at', sa.DateTime, index=True),
        sa.Column('resolved_at', sa.DateTime),
        sa.Column('acknowledged_at', sa.DateTime),
        sa.Column('duration_seconds', sa.Integer),
        sa.Column('acknowledged_by', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('assigned_to', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('actions', postgresql.JSONB, default=[]),
        sa.Column('resolution_notes', sa.Text),
        sa.Column('notification_sent', sa.Boolean, default=False),
        sa.Column('notification_channels', postgresql.JSONB, default=[]),
        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime)
    )

    op.create_index('ix_alert_status_severity', 'system_alerts', ['status', 'severity'])
    op.create_index('ix_alert_started', 'system_alerts', ['started_at'])

    # Admin actions table
    op.create_table(
        'admin_actions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('admin_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('action_type', sa.String(100), nullable=False, index=True),
        sa.Column('resource_type', sa.String(100)),
        sa.Column('resource_id', sa.String(36)),
        sa.Column('description', sa.Text),
        sa.Column('changes', postgresql.JSONB, default={}),
        sa.Column('affected_users', postgresql.JSONB, default=[]),
        sa.Column('reason', sa.Text),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.String(512)),
        sa.Column('success', sa.Boolean, default=True),
        sa.Column('error_message', sa.Text),
        sa.Column('timestamp', sa.DateTime, index=True)
    )

    op.create_index('ix_admin_action_type_time', 'admin_actions', ['action_type', 'timestamp'])
    op.create_index('ix_admin_user_time', 'admin_actions', ['admin_id', 'timestamp'])

    # System health table
    op.create_table(
        'system_health',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('timestamp', sa.DateTime, index=True),
        sa.Column('status', sa.String(20), default="healthy"),
        sa.Column('api_status', sa.String(20)),
        sa.Column('database_status', sa.String(20)),
        sa.Column('redis_status', sa.String(20)),
        sa.Column('ml_service_status', sa.String(20)),
        sa.Column('cpu_usage_percent', sa.Float),
        sa.Column('memory_usage_percent', sa.Float),
        sa.Column('disk_usage_percent', sa.Float),
        sa.Column('active_connections', sa.Integer),
        sa.Column('request_rate', sa.Float),
        sa.Column('error_rate', sa.Float),
        sa.Column('avg_response_time_ms', sa.Float),
        sa.Column('db_connections', sa.Integer),
        sa.Column('db_slow_queries', sa.Integer),
        sa.Column('queue_depth', sa.Integer),
        sa.Column('queue_processing_rate', sa.Float),
        sa.Column('metrics', postgresql.JSONB, default={})
    )

    op.create_index('ix_health_timestamp', 'system_health', ['timestamp'])


def downgrade():
    """Drop all analytics, webhooks, and admin tables."""

    # Admin tables
    op.drop_table('system_health')
    op.drop_table('admin_actions')
    op.drop_table('system_alerts')
    op.drop_table('feature_flags')
    op.drop_table('experiment_assignments')
    op.drop_table('experiment_variants')
    op.drop_table('experiments')

    # Webhook tables
    op.drop_table('webhook_events')
    op.drop_table('webhook_attempts')
    op.drop_table('webhook_deliveries')
    op.drop_table('webhooks')

    # Analytics tables
    op.drop_table('activity_logs')
    op.drop_table('revenue_metrics')
    op.drop_table('user_ltv')
    op.drop_table('cohort_analysis')
    op.drop_table('user_behavior_metrics')
    op.drop_table('feature_usage_stats')
    op.drop_table('user_sessions')
    op.drop_table('events')
