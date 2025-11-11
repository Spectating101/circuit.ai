"""Initial database migration

Revision ID: 001_initial
Revises:
Create Date: 2025-11-11 08:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Upgrade database schema."""

    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255)),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('subscription_plan', sa.String(50), default='free'),
        sa.Column('stripe_customer_id', sa.String(255)),
        sa.Column('metadata', postgresql.JSONB, default={})
    )
    op.create_index('idx_users_email', 'users', ['email'])

    # API Keys table
    op.create_table(
        'api_keys',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('key_hash', sa.String(255), unique=True, nullable=False),
        sa.Column('key_prefix', sa.String(20), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('last_used_at', sa.DateTime()),
        sa.Column('usage_count', sa.Integer(), default=0),
        sa.Column('metadata', postgresql.JSONB, default={})
    )
    op.create_index('idx_api_keys_hash', 'api_keys', ['key_hash'])
    op.create_index('idx_api_keys_user', 'api_keys', ['user_id'])

    # Organizations table
    op.create_table(
        'organizations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), unique=True, nullable=False),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('subscription_tier', sa.String(50), default='free'),
        sa.Column('stripe_customer_id', sa.String(255)),
        sa.Column('monthly_analysis_quota', sa.Integer(), default=100),
        sa.Column('analyses_used_this_month', sa.Integer(), default=0),
        sa.Column('sso_enabled', sa.Boolean(), default=False),
        sa.Column('sso_provider', sa.String(50)),
        sa.Column('sso_domain', sa.String(255)),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('settings', postgresql.JSONB, default={}),
        sa.Column('branding', postgresql.JSONB)
    )
    op.create_index('idx_organizations_slug', 'organizations', ['slug'])

    # Organization Members table
    op.create_table(
        'organization_members',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('invited_by', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('joined_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('last_active_at', sa.DateTime()),
        sa.Column('custom_permissions', postgresql.JSONB)
    )
    op.create_index('idx_org_members_org', 'organization_members', ['organization_id'])
    op.create_index('idx_org_members_user', 'organization_members', ['user_id'])
    op.create_unique_constraint('uq_org_member', 'organization_members', ['organization_id', 'user_id'])

    # Analyses table
    op.create_table(
        'analyses',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='SET NULL')),
        sa.Column('analysis_id', sa.String(255), unique=True, nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('file_hash', sa.String(255)),
        sa.Column('processing_time', sa.Float(), nullable=False),
        sa.Column('components_detected', sa.Integer(), default=0),
        sa.Column('backend_used', sa.String(50), nullable=False),
        sa.Column('ocr_enabled', sa.Boolean(), default=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text()),
        sa.Column('results', postgresql.JSONB),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('metadata', postgresql.JSONB, default={})
    )
    op.create_index('idx_analyses_user', 'analyses', ['user_id'])
    op.create_index('idx_analyses_created', 'analyses', ['created_at'])
    op.create_index('idx_analyses_org', 'analyses', ['organization_id'])

    # Components table
    op.create_table(
        'components',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('analysis_id', sa.String(36), sa.ForeignKey('analyses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('component_type', sa.String(100), nullable=False),
        sa.Column('component_value', sa.String(100)),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('bbox_x1', sa.Float()),
        sa.Column('bbox_y1', sa.Float()),
        sa.Column('bbox_x2', sa.Float()),
        sa.Column('bbox_y2', sa.Float()),
        sa.Column('metadata', postgresql.JSONB, default={})
    )
    op.create_index('idx_components_analysis', 'components', ['analysis_id'])
    op.create_index('idx_components_type', 'components', ['component_type'])

    # Subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE')),
        sa.Column('plan_id', sa.String(50), nullable=False),
        sa.Column('plan_name', sa.String(100), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(255), unique=True),
        sa.Column('stripe_price_id', sa.String(255)),
        sa.Column('current_period_start', sa.DateTime()),
        sa.Column('current_period_end', sa.DateTime()),
        sa.Column('cancel_at_period_end', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('metadata', postgresql.JSONB, default={})
    )
    op.create_index('idx_subscriptions_user', 'subscriptions', ['user_id'])
    op.create_index('idx_subscriptions_org', 'subscriptions', ['organization_id'])

    # Usage Analytics table
    op.create_table(
        'usage_analytics',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='SET NULL')),
        sa.Column('endpoint', sa.String(255), nullable=False),
        sa.Column('method', sa.String(10), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('response_time', sa.Float(), nullable=False),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.Text()),
        sa.Column('request_size', sa.Integer()),
        sa.Column('response_size', sa.Integer()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('metadata', postgresql.JSONB, default={})
    )
    op.create_index('idx_analytics_user', 'usage_analytics', ['user_id'])
    op.create_index('idx_analytics_endpoint', 'usage_analytics', ['endpoint'])
    op.create_index('idx_analytics_created', 'usage_analytics', ['created_at'])

    # Feature Flags table
    op.create_table(
        'feature_flags',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('enabled', sa.Boolean(), default=False),
        sa.Column('rollout_percentage', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('metadata', postgresql.JSONB, default={})
    )

    # Audit Log table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='SET NULL')),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(50)),
        sa.Column('resource_id', sa.String(36)),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.Text()),
        sa.Column('changes', postgresql.JSONB),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()'))
    )
    op.create_index('idx_audit_user', 'audit_logs', ['user_id'])
    op.create_index('idx_audit_org', 'audit_logs', ['organization_id'])
    op.create_index('idx_audit_created', 'audit_logs', ['created_at'])

    # Create updated_at trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    # Apply triggers to tables with updated_at
    for table in ['users', 'organizations', 'subscriptions']:
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """)


def downgrade():
    """Downgrade database schema."""

    # Drop triggers
    for table in ['users', 'organizations', 'subscriptions']:
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};")

    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")

    # Drop tables in reverse order
    op.drop_table('audit_logs')
    op.drop_table('feature_flags')
    op.drop_table('usage_analytics')
    op.drop_table('subscriptions')
    op.drop_table('components')
    op.drop_table('analyses')
    op.drop_table('organization_members')
    op.drop_table('organizations')
    op.drop_table('api_keys')
    op.drop_table('users')
